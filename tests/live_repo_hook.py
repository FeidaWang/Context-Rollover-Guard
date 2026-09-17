"""Explicit production-entrypoint acceptance in a separate persistent fixture workspace."""
import argparse,json,sys,time
from pathlib import Path
from tests.support.live_server import LiveServer
from crg.installer import plan_hooks,install_hooks
from crg.state_store import StateStore

def main():
    from tests.support.live_policy import require_live_authorization
    require_live_authorization('live_repo_hook')
    p=argparse.ArgumentParser();p.add_argument('--scratch',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    scratch=a.scratch.resolve();workspace=scratch/'workspace';workspace.mkdir(parents=True,exist_ok=True);a.out.mkdir(parents=True,exist_ok=True)
    workspace.joinpath('crg.toml').write_text('[context_rollover]\nenabled=true\nmode="MODE_B"\nstate_root=".crg-state"\narchive_root=".archives"\n[predictor]\nhard_arm_remaining_tokens=999999\n')
    script=Path(__file__).resolve().parents[1]/'scripts/repo_hook.py'
    install_hooks(plan_hooks(workspace/'.codex/hooks.json',[sys.executable,'-I',str(script),'--workspace',str(workspace)]),scratch/'receipts')
    server=LiveServer(scratch,'/Applications/ChatGPT.app/Contents/Resources/codex',fixture_hooks=True)
    report={'production_hook_files_changed':False}
    try:
        server.initialize()
        response=server.rpc('thread/start',{'cwd':str(workspace),'model':'gpt-6-astra','ephemeral':False,
            'sandbox':'read-only','approvalPolicy':'never'})
        tid=response['thread']['id'];turn=server.complete_turn(tid,'Reply exactly CRG_REPO_ADAPTER_OK. Do not use tools.')
        state=StateStore(workspace/'.crg-state',workspace,tid).read()
        report.update(session_bound=state.session_id==tid,answer_exact=Path(state.pending_answer_path).read_bytes()==b'CRG_REPO_ADAPTER_OK',
            telemetry_status=state.telemetry.get('repo_adapter',{}).get('telemetry_status'),state=state.state)
        assert report['answer_exact'] and report['session_bound']
        assert report['telemetry_status']=='VERIFIED_ACTIVE_RECORD'
        assert state.state=='ARMED'
        prompt=' 下一条原文\r\n🙂 '
        result=server.rpc('turn/start',{'threadId':tid,'input':[{'type':'text','text':prompt}]})
        blocked_turn=result['turn']['id'];deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            event=server.next();server.collect(event)
            if event.get('method')=='hook/completed' and event['params']['run']['eventName']=='userPromptSubmit':
                assert event['params']['run']['status']=='blocked';break
        else:raise TimeoutError('Guard did not block')
        state=StateStore(workspace/'.crg-state',workspace,tid).read()
        archive=Path(state.telemetry['guard']['archive_dir'])
        assert json.loads((archive/'prompt.json').read_text())['text']==prompt
        report.update(prompt_saved_before_block=True,status='PASS',desktop_switched=False)
        server.rpc('thread/archive',{'threadId':tid})
    except Exception as exc:report.update(status='BLOCKED',error=type(exc).__name__+':'+str(exc)[:200]);raise
    finally:
        server.close();(a.out/'repo-hook-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
