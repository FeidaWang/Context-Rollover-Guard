"""Explicit isolated Desktop read-only transport acceptance; no turns or configuration writes.

Run from the project root with --run. Uses only the installed runtime and loopback.
"""
import base64,hashlib,json,os,socket,struct,subprocess,tempfile,threading,time
from pathlib import Path

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", required=True)
    parser.parse_args()
    root=Path.cwd();tmp=Path(tempfile.mkdtemp(prefix='crg-desktop-bridge-'));os.chmod(tmp,0o700)
    report={'current_instance_modified':False,'isolated_user_data':str(tmp),'methods':[],'responses':[],'backend_requests':[]}
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(25)
    env=os.environ.copy();env['CODEX_ELECTRON_USER_DATA_PATH']=str(tmp/'electron');env['CODEX_APP_SERVER_WS_URL']='ws://127.0.0.1:'+str(listener.getsockname()[1]);env.pop('CODEX_APP_SERVER_FORCE_CLI',None)
    app=None;backend=None;conn=None;lock=threading.Lock();ids={}
    def send(message,opcode=1):
     data=json.dumps(message).encode() if opcode==1 else message
     head=bytes([128|opcode])+ (bytes([len(data)]) if len(data)<126 else b'\x7e'+struct.pack('!H',len(data)) if len(data)<65536 else b'\x7f'+struct.pack('!Q',len(data)))
     with lock:conn.sendall(head+data)
    def read_backend():
     try:
      for raw in backend.stdout:
       msg=json.loads(raw)
       if 'method' in msg and 'id' in msg:report['backend_requests'].append(msg['method'])
       if 'id' in msg and 'method' not in msg:report['responses'].append({'method':ids.get(str(msg['id'])),'success':'result' in msg,'error_code':msg.get('error',{}).get('code')})
       send(msg)
     except (OSError,ValueError):pass
    try:
     backend=subprocess.Popen(['/Applications/ChatGPT.app/Contents/Resources/codex','app-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
     app=subprocess.Popen(['/Applications/ChatGPT.app/Contents/MacOS/ChatGPT','--user-data-dir='+str(tmp/'chromium')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
     conn,_=listener.accept();conn.settimeout(20);stream=conn.makefile('rb');headers={};stream.readline()
     while True:
      line=stream.readline()
      if line==b'\r\n':break
      key,value=line.decode().split(':',1);headers[key.lower()]=value.strip()
     accept=base64.b64encode(hashlib.sha1((headers['sec-websocket-key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
     conn.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
     threading.Thread(target=read_backend,daemon=True).start()
     end=time.monotonic()+35
     while time.monotonic()<end:
      h=stream.read(2)
      if len(h)!=2:break
      opcode=h[0]&15;length=h[1]&127
      if length==126:length=struct.unpack('!H',stream.read(2))[0]
      elif length==127:length=struct.unpack('!Q',stream.read(8))[0]
      if length>8*1024*1024:raise ValueError('oversized')
      mask=stream.read(4) if h[1]&128 else None;data=stream.read(length)
      if mask:data=bytes(b^mask[i%4] for i,b in enumerate(data))
      if opcode==8:break
      if opcode==9:send(data,10);continue
      if opcode!=1:continue
      msg=json.loads(data);method=msg.get('method');report['methods'].append(method)
      if method and 'id'in msg:ids[str(msg['id'])]=method
      allowed=method in {'initialize','initialized','config/read','account/read','account/rateLimits/read','model/list','thread/list','thread/loaded/list','thread/read','project/list','experimentalFeature/list','plugin/list','skills/list','hooks/list','mcpServerStatus/list','apps/list','configRequirements/read','permissionProfile/list'}
      if method and not allowed:
       if 'id'in msg:send({'id':msg['id'],'error':{'code':-32601,'message':'Read-only CRG probe: method unavailable'}})
       continue
      backend.stdin.write(json.dumps(msg).encode()+b'\n');backend.stdin.flush()
    except Exception as exc:report['end_reason']=type(exc).__name__
    finally:
     for p in [app,backend]:
      if p and p.poll() is None:
       p.terminate()
       try:p.wait(timeout=5)
       except subprocess.TimeoutExpired:p.kill();p.wait()
     if conn:conn.close()
     listener.close()
     report['initialize_completed']=any(r['method']=='initialize' and r['success'] for r in report['responses'])
     (root/'docs/context-rollover/evidence/desktop-native-bridge.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__ == "__main__":
    main()
