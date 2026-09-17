"""Bounded stdio test harness. No production proxy, UI switch or credential copying."""
import json
import os
import re
from pathlib import Path
import selectors
import subprocess
import time
import tempfile
import tomllib


class LiveServer:
    def __init__(self, scratch: Path, binary="codex", *, fixture_hooks=False, on_event=None, command_only=False):
        self.scratch=scratch.resolve(); self.scratch.mkdir(parents=True,exist_ok=True)
        self.workspace=self.scratch/'workspace'; self.workspace.mkdir(exist_ok=True)
        self.events=[];self.buffer=b'';self.counter=0
        self.fixture_hooks=fixture_hooks;self.on_event=on_event
        self.home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
        config_path=self.home/'config.toml'
        config=tomllib.loads(config_path.read_text()) if config_path.exists() else {}
        overrides={'features.hooks':fixture_hooks,'features.plugins':False,'features.apps':False,
                   'notify':[],'analytics.enabled':False,
                   'log_dir':str(self.scratch/'logs'),'sqlite_home':str(self.scratch/'sqlite')}
        for name in config.get('mcp_servers',{}):
            if not re.fullmatch(r'[A-Za-z0-9_-]+',name):raise ValueError('unsupported_mcp_override_key')
            overrides['mcp_servers.'+name+'.enabled']=False
        if fixture_hooks:overrides['bypass_hook_trust']=True
        args=[binary]
        for key,value in overrides.items():args+=['-c',key+'='+json.dumps(value)]
        if fixture_hooks:
            args+=['-c','projects={'+json.dumps(str(self.workspace))+'={trust_level="trusted"}}',
                   '--dangerously-bypass-hook-trust']
        args+=['app-server','--stdio']
        self.command=args
        if command_only:return
        # Existing credentials stay in their native store. No auth payload is read or logged here.
        self.error_file=tempfile.TemporaryFile()
        self.proc=subprocess.Popen(args,cwd=self.workspace,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   stderr=self.error_file)
        self.selector=selectors.DefaultSelector();self.selector.register(self.proc.stdout,selectors.EVENT_READ)

    def send(self,message):
        self.proc.stdin.write((json.dumps(message)+'\n').encode());self.proc.stdin.flush()

    def next(self,timeout=30):
        until=time.monotonic()+timeout
        while True:
            if b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1)
                return json.loads(line)
            left=until-time.monotonic()
            if left<=0:raise TimeoutError('live_app_server_timeout')
            if self.selector.select(min(1,left)):
                chunk=os.read(self.proc.stdout.fileno(),65536)
                if not chunk:
                    self.error_file.seek(0);error=self.error_file.read().decode(errors='replace')
                    category='unclassified'
                    for pattern in ('Permission denied','Operation not permitted','No such file','unknown variant','invalid type','missing field','failed to create','Error loading configuration','unknown field'):
                        if pattern in error:category=pattern;break
                    raise RuntimeError('live_app_server_eof:'+category)
                self.buffer+=chunk
            if len(self.buffer)>8*1024*1024:raise RuntimeError('oversized_protocol_frame')

    def collect(self,message):
        if 'id' in message and 'method' in message:
            self.send({'id':message['id'],'error':{'code':-32601,'message':'Test harness does not approve tools'}})
            raise RuntimeError('unexpected_server_request')
        method=message.get('method');p=message.get('params',{})
        if method=='thread/tokenUsage/updated':
            event={'method':method,'params':{k:p[k] for k in ('threadId','turnId','tokenUsage')}}
        elif method=='turn/completed':
            event={'method':method,'params':{'threadId':p['threadId'],
                  'turn':{'id':p['turn']['id'],'status':p['turn']['status']}}}
            if p['turn'].get('error'):
                error=p['turn']['error']
                event['params']['turn']['error']={'codexErrorInfo':error.get('codexErrorInfo'),
                    'message':re.sub(r'(?:sk-[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_.-]+)', '[REDACTED]',error.get('message',''))[:700]}
        elif method=='thread/compacted':
            event={'method':method,'params':{k:p[k] for k in ('threadId','turnId')}}
        elif method=='item/completed' and p.get('item',{}).get('type')=='contextCompaction':
            event={'method':method,'params':{'threadId':p['threadId'],'turnId':p['turnId'],
                                            'item':{'id':p['item']['id'],'type':'contextCompaction'}}}
        elif method in {'hook/started','hook/completed'}:
            run=p['run']
            event={'method':method,'params':{'threadId':p['threadId'],'turnId':p.get('turnId'),
                'run':{k:run[k] for k in ('id','eventName','status','entries') if k in run}}}
        else:return
        self.events.append(event)
        if self.on_event:self.on_event(event)

    def rpc(self,method,params,timeout=30):
        self.counter+=1; ident=self.counter
        self.send({'id':ident,'method':method,'params':params})
        deadline=time.monotonic()+timeout
        while True:
            message=self.next(max(.01,deadline-time.monotonic()))
            if message.get('id')==ident and 'method' not in message:
                if 'error' in message:
                    raise RuntimeError('rpc_error:'+method+':'+str(message['error'].get('code')))
                return message['result']
            self.collect(message)
            if time.monotonic()>=deadline:raise TimeoutError('rpc_timeout:'+method)

    def initialize(self):
        result=self.rpc('initialize',{'clientInfo':{'name':'crg_live_test','version':'0.1.0'},
                                     'capabilities':{'experimentalApi':True}})
        self.send({'method':'initialized'})
        config=self.rpc('config/read',{'cwd':str(self.workspace),'includeLayers':False})['config']
        if config.get('features',{}).get('hooks') is not self.fixture_hooks or config.get('notify') not in ([],None):
            raise RuntimeError('test_isolation_not_verified')
        if any(v.get('enabled',True) for v in config.get('mcp_servers',{}).values()):
            raise RuntimeError('test_mcp_isolation_not_verified')
        return result

    def complete_turn(self,thread,text,timeout=120):
        result=self.rpc('turn/start',{'threadId':thread,'input':[{'type':'text','text':text}],
                                     'effort':'low','approvalPolicy':'never'})
        turn=result['turn']['id'];deadline=time.monotonic()+timeout
        while not any(e['method']=='turn/completed' and e['params']['turn']['id']==turn for e in self.events):
            self.collect(self.next(min(30,max(.01,deadline-time.monotonic()))))
            if time.monotonic()>=deadline:raise TimeoutError('model_turn_timeout')
        completion=next(e for e in self.events if e['method']=='turn/completed' and e['params']['turn']['id']==turn)
        if completion['params']['turn']['status']!='completed':raise RuntimeError('model_turn_not_completed:'+json.dumps(completion['params']['turn'].get('error',{})))
        return turn

    def close(self):
        try:self.proc.stdin.close()
        except OSError:pass
        try:self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        self.proc.stdout.close();self.selector.close();self.error_file.close()
