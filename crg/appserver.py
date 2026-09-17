"""Explicit, version-bound stdio App Server client. No automatic rollover or UI mutation."""
from concurrent.futures import Future,TimeoutError as FutureTimeout
from dataclasses import dataclass
import copy
import hashlib
import shutil
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import threading


class ProtocolError(RuntimeError):pass
class RpcError(ProtocolError):
    def __init__(self,method,error):
        self.method,self.error=method,error
        super().__init__(f'RPC {method} failed (code {error.get("code")})')
class AmbiguousRequest(ProtocolError):
    """Request may have been accepted. Caller must reconcile; never blindly retry."""
    def __init__(self,method):
        self.method=method
        super().__init__(f'Acceptance unknown for {method}; reconciliation required')


class ProtocolSchema:
    def __init__(self,root:Path, *, manifest_path:Path | None = None):
        manifest=json.loads((manifest_path or root.parent/'capabilities.json').read_text())
        self.manifest = manifest
        self.schema_root = root
        if manifest.get('evidence_version') is not None:
            from .capability_evidence import validate
            try:
                root = validate(manifest, root)
            except (ValueError, OSError) as exc:
                raise ProtocolError(str(exc)) from exc
        source=(root/'ClientRequest.json').read_bytes()
        if manifest.get('schema_sha256',{}).get('ClientRequest.json')!=hashlib.sha256(source).hexdigest():
            raise ProtocolError('Generated schema integrity mismatch')
        self.runtime_version=manifest['codex_version'];self.runtime_binary=manifest['binary']
        self.document=json.loads(source)
        self.methods={name:v['properties']['params'] for v in self.document.get('oneOf',[])
                      for name in v.get('properties',{}).get('method',{}).get('enum',[]) if 'params' in v['properties']}

    def _validate(self,value,schema,depth=0):
        if depth>100:raise ValueError('Schema nesting limit')
        if schema is True:return
        if schema is False:raise ValueError('Value forbidden by schema')
        if '$ref' in schema:
            ref=schema['$ref']
            if not ref.startswith('#/definitions/'):raise ValueError('External schema reference unsupported')
            self._validate(value,self.document['definitions'][ref.split('/')[-1]],depth+1)
        for keyword in ('allOf','anyOf','oneOf'):
            if keyword in schema:
                matches=0
                for child in schema[keyword]:
                    try:self._validate(value,child,depth+1);matches+=1
                    except ValueError:pass
                required=len(schema[keyword]) if keyword=='allOf' else 1
                if matches<required or keyword=='oneOf' and matches!=1:raise ValueError('Schema union mismatch')
        types=schema.get('type')
        if types:
            kinds=types if isinstance(types,list) else [types]
            valid={'null':value is None,'boolean':type(value)is bool,'integer':type(value)is int,
                   'number':type(value)in (int,float) and math.isfinite(value),'string':isinstance(value,str),
                   'array':isinstance(value,list),'object':isinstance(value,dict)}
            if not any(valid.get(kind,False) for kind in kinds):raise ValueError('Schema type mismatch')
        if 'enum' in schema and value not in schema['enum']:raise ValueError('Invalid enum')
        if isinstance(value,dict):
            if not set(schema.get('required',[]))<=set(value):raise ValueError('Missing required fields')
            props=schema.get('properties',{});additional=schema.get('additionalProperties',True)
            for key,item in value.items():
                self._validate(item,props[key] if key in props else additional,depth+1)
        if isinstance(value,list):
            if len(value)<schema.get('minItems',0):raise ValueError('Too few array items')
            for item in value:self._validate(item,schema.get('items',True),depth+1)
        if isinstance(value,str):
            if len(value)<schema.get('minLength',0):raise ValueError('String too short')
            if 'pattern' in schema and re.search(schema['pattern'],value)is None:raise ValueError('String pattern mismatch')
        if type(value)in (int,float):
            if 'minimum'in schema and value<schema['minimum']:raise ValueError('Below minimum')
            if 'maximum'in schema and value>schema['maximum']:raise ValueError('Above maximum')

    def validate_action(self, method, params):
        """Reject unsupported constraints before preparing registry action parameters."""
        supported = {'$ref', 'type', 'enum', 'allOf', 'anyOf', 'oneOf', 'properties',
                     'additionalProperties', 'required', 'items', 'minItems', 'minLength',
                     'pattern', 'minimum', 'maximum', 'description', 'title', 'default'}
        visited = set()
        def check(schema):
            if type(schema) is bool:return
            if not isinstance(schema, dict) or set(schema)-supported:
                raise ValueError('Unsupported action schema constraints')
            if id(schema) in visited:return
            visited.add(id(schema))
            if '$ref' in schema:
                ref = schema['$ref']
                if not isinstance(ref, str) or not ref.startswith('#/definitions/'):
                    raise ValueError('Unsupported action schema reference')
                check(self.document['definitions'][ref.split('/')[-1]])
            for child in schema.get('properties', {}).values():check(child)
            for key in ('items', 'additionalProperties'):
                if key in schema:check(schema[key])
            for key in ('allOf', 'anyOf', 'oneOf'):
                for child in schema.get(key, []):check(child)
        if method not in self.methods:raise ValueError('Action method unavailable')
        check(self.methods[method])
        self.validate(method, params)

    def validate(self,method,params):
        if method in {'thread/fork','thread/delete'}:raise ValueError('CRG forbids fork/delete')
        if method not in self.methods:raise ValueError('Method absent from installed schema')
        self._validate(params,self.methods[method])
        # Do not rely on serde ignoring obsolete top-level fields.
        schema=self.methods[method]
        if '$ref'in schema:schema=self.document['definitions'][schema['$ref'].split('/')[-1]]
        if 'properties'in schema and set(params)-set(schema['properties']):raise ValueError('Unrecognized protocol fields')
        if method=='thread/start' and params.get('permissions') is not None and params.get('sandbox') is not None:
            raise ValueError('Mutually exclusive thread permissions')
        if method=='turn/start' and params.get('permissions') is not None and params.get('sandboxPolicy') is not None:
            raise ValueError('Mutually exclusive turn permissions')


class AppServerClient:
    def __init__(self,binary:str,schema:ProtocolSchema,workspace:Path,*,expected_version:str,command=None):
        self.binary,self.schema,self.workspace=binary,schema,workspace.resolve()
        self.expected_version=expected_version
        self.command=list(command) if command else [binary,'app-server','--stdio']
        actual=Path(shutil.which(binary) or binary).resolve()
        if actual!=Path(schema.runtime_binary).resolve() or expected_version!=schema.runtime_version:
            raise ProtocolError('Runtime does not match generated schema provenance')
        if not self.command or Path(shutil.which(self.command[0]) or self.command[0]).resolve()!=actual:
            raise ValueError('Command binary differs from bound runtime')
        self.proc=None;self.pending={};self.lock=threading.Lock();self.counter=0
        self.events=queue.Queue(maxsize=2048);self.failure=None;self.reader=None

    def start(self):
        if self.proc is not None:raise ProtocolError('Client already started')
        from .capability_evidence import validate
        try:
            validate(self.schema.manifest, self.schema.schema_root, binary=self.binary, for_action=True)
        except (ValueError, OSError) as exc:
            raise ProtocolError(str(exc)) from exc
        version=subprocess.run([self.binary,'--version'],capture_output=True,text=True,timeout=10)
        if version.returncode or version.stdout.strip()!=self.expected_version:
            raise ProtocolError('Runtime version changed; regenerate schema and re-probe')
        self.proc=subprocess.Popen(self.command,cwd=self.workspace,stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.reader=threading.Thread(target=self._receive,daemon=True);self.reader.start()
        try:
            result=self.request('initialize',{'clientInfo':{'name':'context_rollover_guard','version':'0.1.0'},
                'capabilities':{'experimentalApi':True}})
            self._send({'method':'initialized'})
            return result
        except BaseException:
            self.close();raise

    def _send(self,message):
        data=(json.dumps(message,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
        with self.lock:
            if self.proc is None or self.failure:raise ProtocolError('App Server unavailable')
            self.proc.stdin.write(data);self.proc.stdin.flush()

    def _receive(self):
        try:
            while True:
                line=self.proc.stdout.readline(32*1024*1024+1)
                if not line:raise ProtocolError('App Server EOF')
                if not line.endswith(b'\n') or len(line)>32*1024*1024:raise ProtocolError('Oversized/incomplete protocol frame')
                event=json.loads(line)
                if not isinstance(event,dict):raise ProtocolError('Invalid protocol envelope')
                if 'id'in event and 'method'not in event:
                    with self.lock:future=self.pending.pop(event['id'],None)
                    if future and not future.done():future.set_result(event)
                else:self.events.put_nowait(event)
        except (OSError,ValueError,ProtocolError,queue.Full) as exc:
            with self.lock:
                self.failure=exc
                pending=list(self.pending.values());self.pending.clear()
            for future in pending:
                if not future.done():future.set_exception(ProtocolError('Protocol stream unavailable'))

    def request(self,method,params,*,timeout=30):
        self.schema.validate(method,params)
        with self.lock:
            if self.failure:raise ProtocolError('Protocol stream unavailable')
            self.counter+=1;ident=self.counter;future=Future();self.pending[ident]=future
        try:
            self._send({'id':ident,'method':method,'params':params})
            response=future.result(timeout=timeout)
        except (OSError,ProtocolError,FutureTimeout) as exc:
            with self.lock:self.pending.pop(ident,None)
            raise AmbiguousRequest(method) from exc
        if 'error'in response:raise RpcError(method,response['error'])
        if 'result'not in response:raise ProtocolError('Malformed RPC response')
        return response['result']

    def next_event(self,timeout=1):
        try:return self.events.get(timeout=timeout)
        except queue.Empty:
            if self.failure:raise ProtocolError('Protocol stream unavailable')
            return None

    def respond(self,ident,*,result=None,error=None):
        self._send({'id':ident,'error':error} if error is not None else {'id':ident,'result':result})

    def close(self):
        if self.proc is None:return
        try:self.proc.stdin.close()
        except OSError:pass
        try:self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        if self.reader:self.reader.join(timeout=3)
        self.proc.stdout.close()


@dataclass(frozen=True)
class ExecutionSettings:
    """Settings observed on an owned thread, not inferred from a Desktop summary."""
    values:dict

    @classmethod
    def from_start(cls,response):
        required=('cwd','model','modelProvider','approvalPolicy','approvalsReviewer','sandbox')
        if any(k not in response for k in required):raise ValueError('Incomplete execution settings')
        if not Path(response['cwd']).is_absolute():raise ValueError('Non-absolute workspace')
        keys=required+('serviceTier','reasoningEffort','runtimeWorkspaceRoots','activePermissionProfile')
        values={k:copy.deepcopy(response.get(k)) for k in keys}
        developer=response.get('developerInstructions')
        values['developer_config_sha256']=hashlib.sha256(developer.encode()).hexdigest() if isinstance(developer,str) else None
        return cls(values)

    def verify_requested(self, params):
        """Refuse a runtime response that widens explicitly requested startup settings."""
        for key in ('cwd', 'model', 'modelProvider', 'approvalPolicy', 'approvalsReviewer', 'serviceTier'):
            if key in params and params[key] != self.values.get(key):
                raise ValueError('Runtime changed requested setting: ' + key)
        if params.get('permissions') is not None:
            profile = self.values.get('activePermissionProfile') or {}
            if profile.get('id') != params['permissions']:
                raise ValueError('Runtime changed requested permission profile')
        if 'sandbox' in params:
            if params['sandbox'] != 'read-only' or self.values['sandbox'] not in (
                    {'type':'readOnly'}, {'type':'readOnly','networkAccess':False}):
                raise ValueError('Requested sandbox not verifiably preserved')
        return True

    def thread_params(self,handoff:str,*,recovery_pointer:str|None=None):
        v=self.values
        result={k:copy.deepcopy(v[k]) for k in ('cwd','model','modelProvider','approvalPolicy','approvalsReviewer','serviceTier')}
        profile=v.get('activePermissionProfile')
        if profile and profile.get('id'):result['permissions']=profile['id']
        elif v['sandbox']=={'type':'readOnly','networkAccess':False} or v['sandbox']=={'type':'readOnly'}:
            result['sandbox']='read-only'
        else:raise ValueError('Exact permissions cannot be reconstructed safely')
        if v.get('runtimeWorkspaceRoots') is not None:result['runtimeWorkspaceRoots']=v['runtimeWorkspaceRoots']
        # Preserve current runtime/project developer configuration. Recovery pointers
        # are separate result data, never a replacement developerInstructions value.
        if recovery_pointer is not None and (not isinstance(recovery_pointer,str) or not Path(recovery_pointer).is_absolute()):
            raise ValueError('Absolute recovery data pointer required')
        return result

    def turn_params(self,thread_id,prompt,client_message_id):
        if not isinstance(prompt,str):raise ValueError('Text-only forwarding currently supported')
        v=self.values
        result={'threadId':thread_id,'input':[{'type':'text','text':prompt}],
                'clientUserMessageId':client_message_id,'cwd':v['cwd'],'model':v['model'],
                'approvalPolicy':copy.deepcopy(v['approvalPolicy']),'approvalsReviewer':v['approvalsReviewer'],
                'serviceTier':v['serviceTier']}
        if v.get('reasoningEffort')is not None:result['effort']=v['reasoningEffort']
        if v.get('activePermissionProfile'):result['permissions']=v['activePermissionProfile']['id']
        else:result['sandboxPolicy']=copy.deepcopy(v['sandbox'])
        return result

    def verify_new_thread(self,response):
        observed=ExecutionSettings.from_start(response).values
        for key in ('cwd','model','modelProvider','approvalPolicy','approvalsReviewer','sandbox','serviceTier',
                    'runtimeWorkspaceRoots','activePermissionProfile'):
            if self.values[key]!=observed[key]:raise ValueError('New thread changed execution setting: '+key)
        if self.values.get('developer_config_sha256') is not None and self.values['developer_config_sha256'] != observed.get('developer_config_sha256'):
            raise ValueError('Current developer configuration changed or is unobservable')
        # Reasoning effort is explicitly reapplied in turn/start; thread/start has no effort field.
        return True
