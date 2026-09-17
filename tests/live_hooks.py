"""Opt-in local fixture-hook runtime acceptance; no production hook configuration writes."""
from pathlib import Path
from dataclasses import replace
import argparse
import hashlib
import json
import shlex
import sys
from tests.support.live_server import LiveServer
from crg.archive import ArchiveManager
from crg.domain import SessionState,Mode
from crg.state_store import StateStore
from crg.config import Config
from crg.hooks import pending_answer
from crg.telemetry import Observer


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scratch',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--codex',required=True)
    args=parser.parse_args();scratch=args.scratch.resolve();out=args.out;out.mkdir(parents=True,exist_ok=True)
    workspace=scratch/'workspace';(workspace/'.codex').mkdir(parents=True,exist_ok=True)
    from crg.installer import plan_hooks,install_hooks,uninstall_hooks
    hook_path=workspace/'.codex/hooks.json'
    fixture_original=b'{  "hooks": {}  }\n'
    hook_path.write_bytes(fixture_original)
    argv=[sys.executable,str(Path(__file__).resolve().parent/'support/fixture_hook.py'),str(scratch)]
    receipt=install_hooks(plan_hooks(hook_path,argv),scratch/'installer-receipts')['receipt']
    report={'kind':'real_fixture_hooks','status':'BLOCKED','production_hooks_changed':False,'automatic_rollover_enabled':False}
    server=None;observer=None
    def event_callback(event):
        if observer:observer.ingest(event)
    try:
        server=LiveServer(scratch,args.codex,fixture_hooks=True,on_event=event_callback)
        init=server.initialize();report['server_user_agent']=init['userAgent']
        listed=server.rpc('hooks/list',{'cwds':[str(workspace)]})
        report['hook_metadata']=[{k:h.get(k) for k in ('eventName','enabled','trustStatus','source','statusMessage')} for entry in listed['data'] for h in entry['hooks']]
        report['parsed_hook_count']=sum(len(x['hooks']) for x in listed['data'])
        if report['parsed_hook_count']!=5:raise RuntimeError('fixture_hook_discovery_not_verified')
        started=server.rpc('thread/start',{'cwd':str(workspace),'model':'gpt-6-astra','ephemeral':True,
            'sandbox':'read-only','approvalPolicy':'never','config':{'bypass_hook_trust':True},
            'developerInstructions':'This is a fixture hook test. Reply exactly as requested. Never use tools.'})
        thread=started['thread']['id'];session=started['thread'].get('sessionId') or thread
        (scratch/'fixture-settings.json').write_text(json.dumps({'thread_id':thread,'session_id':session}))
        store=StateStore(scratch/'crg-state',workspace,session)
        initial=replace(SessionState.create(workspace,session,thread),mode=Mode.B.value)
        store.update(lambda s:s,initial=initial);observer=Observer(store,Config())
        turn=server.complete_turn(thread,'Reply exactly CRG_HOOK_LOSSLESS_中文_OK.')
        inputs=list((scratch/'hook-inputs').glob('Stop-*.json'))
        if not inputs:raise RuntimeError('fixture_stop_did_not_execute')
        event=json.loads(inputs[0].read_text());answer=pending_answer(store.read())
        if answer!=event['last_assistant_message'].encode():raise RuntimeError('lossless_answer_mismatch')
        prompt=' 原样后续 prompt\r\n🙂\n'
        archive=ArchiveManager(scratch/'archives');folder=archive.prepare(store.read(),prompt,answer)
        checks=archive.verify(folder)
        warning_entries=[entry for e in server.events if e['method']=='hook/completed' and e['params']['run']['eventName']=='stop'
                         for entry in e['params']['run'].get('entries',[]) if entry.get('kind')=='warning']
        if not warning_entries:raise RuntimeError('system_message_not_surfaced')
        report.update(status='PASS',thread_id=thread,turn_id=turn,state=store.read().state,
                      stop_input_fields=sorted(event),answer_sha256=hashlib.sha256(answer).hexdigest(),
                      lossless_answer_verified=True,warning_entries=len(warning_entries),archive_verified=checks['verified'],
                      prompt_exact=json.loads((folder/'prompt.json').read_text())['text']==prompt,
                      fixture_hooks_only=True)
    except (OSError,ValueError,RuntimeError,TimeoutError) as exc:report['error']=str(exc)
    finally:
        if server:
            (out/'hook-events.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in server.events if e['method'].startswith('hook/')))
            server.close()
        uninstall_hooks(receipt)
        report['installer_uninstaller_roundtrip']=hook_path.read_bytes()==fixture_original
        (out/'hook-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
