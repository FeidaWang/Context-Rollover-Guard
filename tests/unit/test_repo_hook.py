from pathlib import Path
import tempfile,json,unittest
from crg.repo_hook import dispatch_repo,transcript_events
from crg.state_store import StateStore

class RepoHookTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve()
        (self.root/'crg.toml').write_text('[context_rollover]\nenabled=true\nmode="MODE_B"\nstate_root=".state"\narchive_root=".archives"\n')
        self.home=self.root/'native';self.sessions=self.home/'sessions';self.sessions.mkdir(parents=True)
        self.log=self.sessions/'fixture.jsonl';self.base={'cwd':str(self.root),'session_id':'session','turn_id':'turn'}
        usage={k:1 for k in ['input_tokens','output_tokens','cached_input_tokens','reasoning_output_tokens']};usage['total_tokens']=100
        self.rows=[{'type':'session_meta','payload':{'id':'session','cli_version':'0.153.4'}},
                   {'type':'event_msg','payload':{'type':'task_started','turn_id':'turn','model_context_window':100000}},
                   {'type':'turn_context','payload':{'turn_id':'turn','cwd':str(self.root)}},
                   {'type':'token_usage_record','payload':{'thread_id':'session','turn_id':'turn','usage':usage,'thread_token_usage':usage|{'total_tokens':999999}}}]
        self.log.write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
    def test_native_active_never_cumulative(self):
        result=transcript_events(self.log,session='session',cwd=self.root,version='0.153.4',allowed_root=self.sessions)
        self.assertEqual(result[0]['params']['tokenUsage']['last']['totalTokens'],100)
        self.assertEqual(result[0]['params']['tokenUsage']['total']['totalTokens'],999999)
    def test_dynamic_session_and_lossless_stop(self):
        self.assertEqual(dispatch_repo(self.base|{'hook_event_name':'SessionStart'},self.root,native_home=self.home),{})
        dispatch_repo(self.base|{'hook_event_name':'Stop','last_assistant_message':'原文\r\n🙂','transcript_path':str(self.log)},self.root,native_home=self.home)
        state=StateStore(self.root/'.state',self.root,'session').read()
        self.assertEqual(Path(state.pending_answer_path).read_bytes(),'原文\r\n🙂'.encode())
        self.assertEqual(state.telemetry['repo_adapter']['telemetry_status'],'VERIFIED_ACTIVE_RECORD')
    def test_null_transcript_keeps_answer_and_no_guessed_pressure(self):
        dispatch_repo(self.base|{'hook_event_name':'Stop','last_assistant_message':'answer','transcript_path':None},self.root,native_home=self.home)
        state=StateStore(self.root/'.state',self.root,'session').read()
        self.assertEqual(state.telemetry['guard']['stop_prediction']['decision'],'UNKNOWN')
        self.assertEqual(Path(state.pending_answer_path).read_bytes(),b'answer')
    def test_wrong_identity_and_version_rejected(self):
        for args in [{'session':'other','version':'0.153.4'},{'session':'session','version':'future'}]:
            with self.assertRaises(ValueError):transcript_events(self.log,cwd=self.root,allowed_root=self.sessions,**args)
    def test_other_workspace_not_sampled(self):
        self.assertEqual(transcript_events(self.log,session='session',cwd=self.root/'other',version='0.153.4',allowed_root=self.sessions),[])
    def test_foreign_path_rejected(self):
        with self.assertRaises(ValueError):transcript_events(self.log,session='session',cwd=self.root,version='0.153.4',allowed_root=self.root/'elsewhere')
    def test_incomplete_tail_ignored(self):
        with self.log.open('a') as f:f.write('{')
        self.assertEqual(len(transcript_events(self.log,session='session',cwd=self.root,version='0.153.4',allowed_root=self.sessions)),1)
