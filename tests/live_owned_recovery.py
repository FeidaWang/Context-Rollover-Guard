"""Opt-in test: lose local completion receipt, reconcile without resubmission."""
from pathlib import Path
import json,time
from crg.appserver import ProtocolSchema,AppServerClient
from crg.config import load_config
from crg.owned_client import OwnedSession
from crg.owned_recovery import reconcile_run

class LostCompletion(OwnedSession):
    def record(self,name,value):
        if name.endswith('-completed'):
            raise RuntimeError('Simulated loss before completion receipt')
        return super().record(name,value)

def main():
    root=Path.cwd();schema=ProtocolSchema(root/'docs/context-rollover/evidence/schema')
    client=AppServerClient(schema.runtime_binary,schema,root,expected_version=schema.runtime_version,
        command=[schema.runtime_binary,'-c','features.hooks=true','app-server','--stdio'])
    config=load_config(root);report={'synthetic_receipt_loss':True,'trust_bypass':False}
    try:
        client.start();session=LostCompletion(client,config,timeout=90);session.start({'sandbox':'read-only'})
        try:session.submit('Reply exactly CRG_RECOVERY_VERIFIED. Do not use tools.')
        except RuntimeError as exc:
            assert str(exc)=='Simulated loss before completion receipt'
        else:raise AssertionError('Receipt-loss fault not reached')
        deadline=time.monotonic()+20
        while True:
            result=reconcile_run(session.root,client,config)
            if result['state']=='READY_TO_RESUME':break
            if time.monotonic()>=deadline:raise AssertionError(result)
            time.sleep(.5)
        resumed=OwnedSession(client,config,timeout=90);resumed.resume(session.root)
        native=client.request('thread/read',{'threadId':session.thread,'includeTurns':True})['thread']
        messages=[i for t in native['turns'] for i in t['items'] if i['type']=='userMessage']
        assert len(messages)==1
        report.update(status='PASS',prompt_sent_once=True,completion_reconciled=True,resumed_same_thread=resumed.thread==session.thread,
            journal=str(session.root),thread_id=session.thread)
        client.request('thread/archive',{'threadId':session.thread})
    finally:
        client.close();(root/'docs/context-rollover/evidence/owned-recovery-live.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
if __name__=='__main__':main()
