"""Child-process death fixture; only synthetic test state."""
import json,os,sys
from pathlib import Path
from tests.unit.test_coordinator import FakeClient
from crg.coordinator import Coordinator
root=Path(sys.argv[1]);rid=sys.argv[2];boundary=sys.argv[3]
client=FakeClient(root);original=client.request

def request(method,params):
    result=original(method,params)
    fd=os.open(root/'child-rpcs.jsonl',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:os.write(fd,(json.dumps({'method':method})+'\n').encode());os.fsync(fd)
    finally:os.close(fd)
    return result
client.request=request
c=Coordinator(root/'transactions',root/'archives',client,owned_surface=True,
              fault=lambda step:os._exit(77) if step==boundary else None)
c.run(rid)
raise SystemExit(1)
