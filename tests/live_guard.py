"""Real guarded-hook acceptance on ephemeral fixture threads only."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import shlex
import sys
import time
from tests.support.live_server import LiveServer
from crg.domain import SessionState,Mode
from crg.state_store import StateStore
from crg.config import Config
from crg.telemetry import Observer


def main():
    from tests.support.live_policy import require_live_authorization
    require_live_authorization('live_guard')
    parser=argparse.ArgumentParser();parser.add_argument('--scratch',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--codex',required=True)
    args=parser.parse_args();scratch=args.scratch.resolve();out=args.out;out.mkdir(parents=True,exist_ok=True)
    workspace=scratch/'workspace';(workspace/'.codex').mkdir(parents=True,exist_ok=True)
    command=shlex.join([sys.executable,str(Path(__file__).resolve().parent/'support/fixture_hook.py'),str(scratch)])
    (workspace/'.codex/hooks.json').write_text(json.dumps({'hooks':{event:[{'hooks':[{'type':'command','command':command,'timeout':10}]}]
        for event in ['SessionStart','Stop','UserPromptSubmit','PreCompact','PostCompact']}}))
    report={'kind':'real_guarded_fixture','status':'BLOCKED','production_hooks_changed':False,
            'desktop_migrated':False,'original_thread_archived':False}
    server=None;observer=None;store=None
    def callback(event):
        if observer and store.read().state in {'NORMAL','ARMED'}:observer.ingest(event)
    def start(*,prompt_block,precompact_block,compact_limit=None):
        nonlocal store,observer
        config={}
        if compact_limit is not None:config['model_auto_compact_token_limit']=compact_limit
        response=server.rpc('thread/start',{'cwd':str(workspace),'model':'gpt-6-astra','ephemeral':True,
            'sandbox':'read-only','approvalPolicy':'never','config':config,
            'developerInstructions':'This is a hook integration test. Reply only with the requested marker, even if input includes padding. Never use tools.'})
        thread=response['thread']['id'];session=response['thread'].get('sessionId') or thread
        (scratch/'fixture-settings.json').write_text(json.dumps({'thread_id':thread,'session_id':session,
            'prompt_block':prompt_block,'precompact_block':precompact_block}))
        store=StateStore(scratch/'crg-state',workspace,session)
        store.update(lambda s:s,initial=replace(SessionState.create(workspace,session,thread),mode=Mode.B.value))
        observer=Observer(store,Config())
        return thread
    def submit_wait(thread,text):
        result=server.rpc('turn/start',{'threadId':thread,'input':[{'type':'text','text':text}],'effort':'low','approvalPolicy':'never'})
        turn=result['turn']['id'];deadline=time.monotonic()+90
        while not any(e['method']=='turn/completed' and e['params']['turn']['id']==turn for e in server.events):
            server.collect(server.next(30))
            if time.monotonic()>deadline:raise TimeoutError('guarded_turn_timeout')
        return turn
    try:
        server=LiveServer(scratch,args.codex,fixture_hooks=True,on_event=callback);server.initialize()
        thread=start(prompt_block=True,precompact_block=False)
        server.complete_turn(thread,'Reply exactly CRG_GUARD_SEED.')
        if store.read().state!='ARMED':raise RuntimeError('fixture_not_armed')
        original=' 原样阻断测试\r\n🙂\n'
        turn=submit_wait(thread,original)
        blocked=[e for e in server.events if e['method']=='hook/completed' and e['params'].get('turnId')==turn
                 and e['params']['run']['eventName']=='userPromptSubmit' and e['params']['run']['status']=='blocked']
        if not blocked:raise RuntimeError('runtime_prompt_block_not_verified')
        if any(e['method']=='thread/tokenUsage/updated' and e['params']['turnId']==turn for e in server.events):
            raise RuntimeError('blocked_prompt_reached_inference')
        archived=Path(store.read().telemetry['guard']['archive_dir'])
        report['prompt_exact']=json.loads((archived/'prompt.json').read_text())['text']==original
        report['prompt_blocked_before_inference']=True
        report['prompt_guard_state']=store.read().state
        observer=None
        thread=start(prompt_block=False,precompact_block=True,compact_limit=14000)
        # A small real seed answer precedes the auto compact trigger.
        server.complete_turn(thread,'Reply exactly CRG_EMERGENCY_SEED.')
        turn=submit_wait(thread,'Reply exactly CRG_SHOULD_NOT_EXECUTE. Padding: '+'x '*16000)
        pre=[json.loads(p.read_text()) for p in (scratch/'hook-inputs').glob('PreCompact-*.json')]
        if not any(e.get('trigger')=='auto' for e in pre):
            # This runtime can use last completed usage to decide compaction at the next turn.
            turn=submit_wait(thread,'Reply exactly CRG_AFTER_LARGE_TURN.')
            pre=[json.loads(p.read_text()) for p in (scratch/'hook-inputs').glob('PreCompact-*.json')]
        if not any(e.get('trigger')=='auto' for e in pre):raise RuntimeError('automatic_precompact_not_observed')
        stopped=[e for e in server.events if e['method']=='hook/completed' and e['params'].get('turnId')==turn
                 and e['params']['run']['eventName']=='preCompact' and e['params']['run']['status']=='stopped']
        if not stopped:raise RuntimeError('runtime_precompact_stop_not_verified')
        if store.read().state!='EMERGENCY':raise RuntimeError('emergency_state_missing')
        report.update(status='PASS',automatic_precompact_seen=True,precompact_stopped=True,
                      snapshot_exists=Path(store.read().telemetry['guard']['emergency_snapshot']).exists(),
                      precompact_input_fields=sorted(pre[-1]),runtime='0.153.4')
    except (OSError,ValueError,RuntimeError,TimeoutError) as exc:report['error']=str(exc)
    finally:
        if server:
            # Raw hook messages can contain fixture prompt text; export event kinds/status only.
            projection=[{'method':e['method'],'turn_id':e['params'].get('turnId') or e['params'].get('turn',{}).get('id'),
                         'hook_event':e['params'].get('run',{}).get('eventName'),
                         'hook_status':e['params'].get('run',{}).get('status')} for e in server.events]
            (out/'event-order.json').write_text(json.dumps(projection,indent=2)+'\n');server.close()
        (out/'guard-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
