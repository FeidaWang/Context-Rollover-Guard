"""Opt-in full owned-surface transaction and ambiguous-forward recovery fixture."""
import argparse,json,time
from dataclasses import replace
from pathlib import Path
from crg.appserver import AppServerClient,ProtocolSchema,ExecutionSettings
from crg.coordinator import Coordinator
from crg.recovery import reconcile_forward
from crg.domain import SessionState,State
from crg.archive import sha
from crg.durable import immutable_write
from tests.support.live_server import LiveServer

class SimulatedCrash(BaseException):pass

def complete(client,turn):
    deadline=time.monotonic()+150;answer=None;compacted=False
    while time.monotonic()<deadline:
        e=client.next_event(1)
        if not e:continue
        if 'id' in e and 'method' in e:raise RuntimeError('Unexpected server request')
        p=e.get('params',{})
        if e.get('method')=='item/completed' and p.get('turnId')==turn:
            if p['item']['type']=='agentMessage':answer=p['item']['text']
            if p['item']['type']=='contextCompaction':compacted=True
        if e.get('method')=='turn/completed' and p['turn']['id']==turn:
            assert p['turn']['status']=='completed';return answer,compacted
    raise TimeoutError('Model completion')

def main():
    p=argparse.ArgumentParser();p.add_argument('--scratch',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--recover',action='store_true');a=p.parse_args()
    schema=ProtocolSchema(Path('docs/context-rollover/evidence/schema'));fixture=LiveServer(a.scratch,schema.runtime_binary,command_only=True)
    client=AppServerClient(schema.runtime_binary,schema,fixture.workspace,expected_version=schema.runtime_version,command=fixture.command)
    report={'production_enabled':False,'desktop_switched':False,'runtime':schema.runtime_version};a.out.mkdir(parents=True,exist_ok=True)
    try:
        client.start()
        original=client.request('thread/start',{'cwd':str(fixture.workspace),'model':'gpt-6-astra','approvalPolicy':'never','sandbox':'read-only','ephemeral':False})
        old=original['thread']['id']
        turn=client.request('turn/start',{'threadId':old,'input':[{'type':'text','text':'CRG isolated test. Reply exactly: Fixture answer 中文. Do not use tools.'}],'effort':'low'})['turn']['id']
        answer,_=complete(client,turn);assert answer is not None
        cache=fixture.scratch/'answer.md';immutable_write(cache,answer.encode())
        state=replace(SessionState.create(fixture.workspace,old,old),state=State.ARMED.value,last_turn_id=turn,
                      pending_answer_path=str(cache),telemetry={'guard':{'pending_answer':{'path':str(cache),'sha256':sha(answer.encode()),'turn_id':turn}}})
        settings=ExecutionSettings.from_start(original);prompt='CRG continuation 中文\r\nReply only OK. Do not use tools.  '
        coordinator=Coordinator(fixture.scratch/'transactions',fixture.scratch/'archives',client,owned_surface=True)
        rid=coordinator.prepare(state,prompt,settings)
        if a.recover:
            coordinator.fault=lambda step:(_ for _ in ()).throw(SimulatedCrash()) if step=='forward:accepted' else None
            try:coordinator.run(rid)
            except SimulatedCrash:pass
            else:raise AssertionError('Fault not reached')
            coordinator.fault=lambda _:None
            assert coordinator.run(rid)['state']=='RECOVERY_REQUIRED'
            deadline=time.monotonic()+90
            while True:
                recovery=reconcile_forward(coordinator,rid)
                if recovery['state']=='ROLLOVER_ARCHIVING':break
                report['initial_recovery_reason']=recovery.get('reason')
                if time.monotonic()>deadline:raise RuntimeError('Readback never confirmed: '+str(recovery.get('reason')))
                time.sleep(.5)
            report['recovery_reason']=recovery.get('reason')
            report['positive_reconciliation']=True
        result=coordinator.run(rid);assert result['old_thread_archived']
        _,compacted=complete(client,result['accepted_turn_id'])
        read=client.request('thread/read',{'threadId':result['new_thread_id'],'includeTurns':True})['thread']
        messages=[i for t in read['turns'] for i in t['items'] if i['type']=='userMessage']
        assert len(messages)==1 and messages[0]['content'][0]['text']==prompt
        assert read['cwd']==state.cwd and result['new_thread_id']!=old
        assert coordinator.run(rid)==result
        archived=client.request('thread/list',{'archived':True,'cwd':state.cwd,'limit':100})
        assert any(t['id']==old for t in archived['data'])
        report.update(status='PASS',prompt_exact_once=True,old_archived_after_acceptance=True,same_cwd=True,
                      fresh_thread=True,no_compaction=not compacted,lossless_answer=(coordinator.archives.root/rid/'answer.md').read_bytes()==answer.encode())
        client.request('thread/archive',{'threadId':result['new_thread_id']})
    except Exception as exc:
        report.update(status='BLOCKED',error_type=type(exc).__name__,error=str(exc)[:300]);raise
    finally:
        client.close();(a.out/'coordinator-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
