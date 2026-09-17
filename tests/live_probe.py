"""Explicit real-model telemetry test: python3.13 -m tests.live_probe --scratch ...

Uses a short-lived ephemeral test thread; never migrates the active Desktop task.
Not included in unittest discovery. Saves projected counters only, not model text.
"""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime,timezone
from tests.support.live_server import LiveServer
from crg.config import Config
from crg.domain import SessionState
from crg.state_store import StateStore
from crg.telemetry import Observer


def main():
    from tests.support.live_policy import require_live_authorization
    require_live_authorization('live_probe')
    p=argparse.ArgumentParser();p.add_argument('--scratch',type=Path,required=True)
    p.add_argument('--codex',default='codex');p.add_argument('--out',type=Path,required=True);p.add_argument('--compact',action='store_true')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    evidence={'kind':'real_model_isolated_test','production_hooks_changed':False,'desktop_migrated':False,
              'generated_at':datetime.now(timezone.utc).isoformat(),'status':'BLOCKED'}
    server=None
    try:
        server=LiveServer(args.scratch,args.codex);init=server.initialize()
        evidence['server_user_agent']=init.get('userAgent')
        response=server.rpc('thread/start',{'cwd':str(server.workspace),'model':'gpt-6-astra',
            'ephemeral':True,'sandbox':'read-only','approvalPolicy':'never',
            'developerInstructions':'This is a telemetry integration test. Reply only with the requested marker. Do not use tools.'})
        thread=response['thread']['id'];evidence['thread_id']=thread
        evidence['ephemeral']=response['thread'].get('ephemeral')
        evidence['same_cwd']=response['cwd']==str(server.workspace)
        if evidence['ephemeral'] is not True or not evidence['same_cwd']:raise RuntimeError('thread_isolation_not_verified')
        store=StateStore(args.scratch.resolve()/'crg-state',server.workspace,thread)
        observer=Observer(store,Config(),initial=SessionState.create(server.workspace,thread,thread))
        cursor=0
        for number in range(1,4):
            turn=server.complete_turn(thread,f'Reply exactly CRG_LIVE_{number}.')
            for event in server.events[cursor:]:observer.ingest(event)
            cursor=len(server.events)
            print(json.dumps({'completed_test_turn':number,'turn_id':turn}),flush=True)
        if args.compact:
            import time
            server.rpc('thread/compact/start',{'threadId':thread})
            deadline=time.monotonic()+90
            while not any(e['method']=='thread/compacted' or
                e['method']=='item/completed' and e['params']['item']['type']=='contextCompaction' for e in server.events[cursor:]):
                server.collect(server.next(30))
                if time.monotonic()>deadline:raise TimeoutError('manual_compaction_timeout')
            for event in server.events[cursor:]:observer.ingest(event)
            cursor=len(server.events)
            server.complete_turn(thread,'Reply exactly CRG_AFTER_COMPACT.')
            for event in server.events[cursor:]:observer.ingest(event)
        state=store.read()
        evidence.update(status='PASS',completed_turns=len(state.telemetry['completed_ids']),
            conversation_turns=sum(x.get('kind')=='conversation' for x in state.telemetry['samples']),
            compaction_turns=sum(x.get('kind')=='compaction' for x in state.telemetry['samples']),
            samples=state.telemetry['samples'],positive_deltas=state.telemetry['positive_deltas'],
            last_prediction=state.telemetry.get('last_prediction'),state=state.state,
            manual_compaction_requested=args.compact,series=state.telemetry['series'])
    except (OSError,ValueError,RuntimeError,TimeoutError) as exc:
        evidence['error']=str(exc)
        print(json.dumps({'blocked':str(exc)}),flush=True)
    finally:
        if server:
            (args.out/'live-events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in server.events))
            server.close()
        (args.out/'live-validation.json').write_text(json.dumps(evidence,indent=2)+'\n')
    return 0 if evidence['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
