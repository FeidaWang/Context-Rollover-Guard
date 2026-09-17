from pathlib import Path
import json,tempfile,unittest
from crg.installer import plan_hooks,install_hooks,uninstall_hooks
from crg.calibration import summarize
from crg.retry import read_with_backoff
from crg.appserver import RpcError

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve()
        self.path=self.root/'hooks.json';self.before=b'{"custom":42,"hooks":{"Stop":[{"hooks":[{"type":"command","command":"existing-user-command"}]}]}}\n'
        self.path.write_bytes(self.before);self.args=['/safe/python','/safe/crg_hook.py','--workspace','/space here']
    def test_merge_and_exact_uninstall(self):
        plan=plan_hooks(self.path,self.args);result=install_hooks(plan,self.root/'receipts')
        data=json.loads(self.path.read_text());self.assertEqual(data['custom'],42)
        self.assertEqual(data['hooks']['Stop'][0]['hooks'][0]['command'],'existing-user-command')
        self.assertEqual(len(data['hooks']['Stop']),2)
        self.assertFalse(install_hooks(plan,self.root/'receipts')['changed'])
        self.assertFalse(install_hooks(plan_hooks(self.path,self.args),self.root/'receipts')['changed'])
        uninstall_hooks(result['receipt']);self.assertEqual(self.path.read_bytes(),self.before)
    def test_concurrent_edit_refused(self):
        plan=plan_hooks(self.path,self.args);self.path.write_bytes(b'{"hooks":{},"user":"changed"}')
        with self.assertRaises(ValueError):install_hooks(plan,self.root/'receipts')
        self.assertEqual(json.loads(self.path.read_text())['user'],'changed')
    def test_uninstall_preserves_later_user_entries(self):
        receipt=install_hooks(plan_hooks(self.path,self.args),self.root/'receipts')['receipt']
        data=json.loads(self.path.read_text());data['new-user-field']=7
        data['hooks']['Stop'].append({'hooks':[{'type':'command','command':'later-user-command'}]})
        self.path.write_text(json.dumps(data));uninstall_hooks(receipt)
        data=json.loads(self.path.read_text());self.assertEqual(data['new-user-field'],7)
        self.assertEqual(len(data['hooks']['Stop']),2)
    def test_symlink_refused(self):
        link=self.root/'link';link.symlink_to(self.path)
        with self.assertRaises(ValueError):plan_hooks(link,self.args)
    def test_missing_original_retains_empty_file(self):
        path=self.root/'new.json';r=install_hooks(plan_hooks(path,self.args),self.root/'receipts')
        uninstall_hooks(r['receipt']);self.assertEqual(json.loads(path.read_text()),{'hooks':{}})
    def test_failed_install_cannot_uninstall_user_file(self):
        plan=plan_hooks(self.path,self.args);self.path.write_bytes(b'{"hooks":{},"user":true}')
        with self.assertRaises(ValueError):install_hooks(plan,self.root/'receipts')
        receipt=next(p for p in (self.root/'receipts').iterdir() if p.is_dir())
        with self.assertRaises(ValueError):uninstall_hooks(receipt)
        self.assertTrue(json.loads(self.path.read_text())['user'])

class CalibrationTests(unittest.TestCase):
    def row(self,i):return {'verified_real':True,'model':'m','runtime_version':'v','limit_scope':'total','event_id':str(i),
        'active_context_tokens':1000,'observed_compact_limit':1200,'automatic_precompact':True,'armed_before':True}
    def test_minimum_samples_and_no_config_mutation(self):
        self.assertEqual(summarize([self.row(0)])[0]['status'],'INSUFFICIENT_REAL_BOUNDARIES')
        report=summarize([self.row(i) for i in range(20)])[0]
        self.assertEqual(report['suggested_conservative_limit'],1200);self.assertFalse(report['configuration_changed'])
    def test_duplicates_do_not_create_confidence(self):
        self.assertEqual(summarize([self.row(1)]*30)[0]['samples'],1)
    def test_synthetic_ignored_and_cumulative_not_substituted(self):
        self.assertEqual(summarize([self.row(0)|{'verified_real':False}]),[])
        row=self.row(1);del row['active_context_tokens'];row['session_tokens']=1000
        with self.assertRaises(ValueError):summarize([row])
    def test_metrics_require_observed_outcomes(self):
        rows=[self.row(1)|{'warning_lead_turns':1},self.row(2)|{'armed_before':False},
              self.row(3)|{'automatic_precompact':False,'outcome_observed':True},
              self.row(4)|{'automatic_precompact':False,'outcome_observed':True,'armed_before':False},
              self.row(5)|{'automatic_precompact':False}]
        r=summarize(rows)[0]
        self.assertEqual(r['evaluated_outcomes'],4)
        self.assertEqual(r['precision'],.5);self.assertEqual(r['recall'],.5)
        self.assertEqual(r['false_positive_rate'],.5);self.assertEqual(r['median_warning_lead_turns'],1)

    def test_version_and_model_separate(self):
        rows=[self.row(i) for i in range(19)]+[self.row(20)|{'runtime_version':'new'}]
        self.assertTrue(all(r['status']=='INSUFFICIENT_REAL_BOUNDARIES' for r in summarize(rows)))

class RetryTests(unittest.TestCase):
    def test_only_explicit_read_overload_retried(self):
        class Client:
            calls=0
            def request(self,m,p):
                self.calls+=1
                if self.calls<3:raise RpcError(m,{'code':123,'fixture_retryable':True})
                return {'ok':True}
        client=Client();delays=[]
        self.assertTrue(read_with_backoff(client,'thread/read',{},retryable=lambda e:e.get('fixture_retryable'),sleep=delays.append)['ok'])
        self.assertEqual(delays,[.1,.2])
        with self.assertRaises(ValueError):read_with_backoff(client,'turn/start',{})
