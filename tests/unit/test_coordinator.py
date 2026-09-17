from tests.support.fixtures import fixture_path
from dataclasses import replace
from pathlib import Path
import copy,json,tempfile,unittest
from concurrent.futures import ThreadPoolExecutor
from crg.coordinator import Coordinator,TransactionError
from crg.recovery import reconcile_forward,reconcile_archive,transaction_status
from crg.appserver import ProtocolSchema,ExecutionSettings,AmbiguousRequest
from crg.domain import SessionState,State
from crg.archive import sha
from crg.durable import immutable_write,private_directory

ROOT=Path(__file__).resolve().parents[2]
class Crash(BaseException):pass
class FakeClient:
    def read_activity(self, thread_id):
        return {'thread_id':thread_id,'complete':True,'turn_state':'completed','tools':[],'children':[]}

    def __init__(self,cwd):
        self.workspace=cwd;self.schema=ProtocolSchema(fixture_path('protocol/schema'));self.calls=[]
        self.response={'cwd':str(cwd),'model':'m','modelProvider':'openai','approvalPolicy':'never','approvalsReviewer':'user',
                       'sandbox':{'type':'readOnly','networkAccess':False},'reasoningEffort':'low',
                       'thread':{'id':'new','cwd':str(cwd),'turns':[]}}
        self.messages=[];self.fail=None
    def request(self,method,params):
        self.schema.validate(method,params);self.calls.append((method,copy.deepcopy(params)))
        if self.fail==method:raise AmbiguousRequest(method)
        if method=='thread/start':return copy.deepcopy(self.response)
        if method=='turn/start':
            self.messages.append({'type':'userMessage','clientId':params['clientUserMessageId'],'content':params['input']})
            return {'turn':{'id':'turn-new','status':'inProgress'}}
        if method=='thread/archive':return {}
        if method=='thread/read':return {'thread':{'id':'new','cwd':str(self.workspace),'turns':[{'id':'turn-new','status':'completed','items':self.messages}]}}
        raise AssertionError(method)

class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.client=FakeClient(self.root);answer=self.root/'answer.md';immutable_write(answer,'上一轮\r\n🙂'.encode())
        self.state=replace(SessionState.create(self.root,'s','old'),state=State.ARMED.value,last_turn_id='previous',
                           pending_answer_path=str(answer),telemetry={'guard':{'pending_answer':{'path':str(answer),'turn_id':'previous','sha256':sha(answer.read_bytes())}}})
        self.c=Coordinator(self.root/'transactions',self.root/'archives',self.client,owned_surface=True)
        self.settings=ExecutionSettings.from_start(self.client.response);self.prompt=' 原文\r\n🙂  '
        self.rid=self.c.prepare(self.state,self.prompt,self.settings)
    def test_unknown_activity_retains_source_without_replay(self):
        self.client.read_activity = lambda thread: {'thread_id':thread,'complete':False}
        result = self.c.run(self.rid)
        self.assertFalse(result['old_thread_archived'])
        self.assertEqual(self.c.run(self.rid), result)
        self.assertEqual([m for m,p in self.client.calls], ['thread/start','turn/start'])

    def test_archival_disabled_retains_source_even_at_quiet_point(self):
        self.c.archive_source=False
        result=self.c.run(self.rid)
        self.assertFalse(result['old_thread_archived'])
        self.assertEqual(result['source_retention_reason'],'ARCHIVAL_DISABLED')

    def test_active_child_retains_source(self):
        self.client.read_activity = lambda thread: {'thread_id':thread,'complete':True,
            'turn_state':'completed','tools':[],'children':[{'state':'running'}]}
        self.assertFalse(self.c.run(self.rid)['old_thread_archived'])

    def test_local_deduplication_and_durable_receipt(self):
        result=self.c.run(self.rid);self.assertTrue(result['old_thread_archived']);self.assertFalse(result['desktop_switched'])
        self.assertEqual(self.c.run(self.rid),result)
        self.assertEqual([m for m,p in self.client.calls],['thread/start','turn/start','thread/archive'])
        self.assertEqual(self.client.messages[0]['content'][0]['text'],self.prompt)
        self.assertEqual(transaction_status(self.c,self.rid)['state'],'NORMAL')
    def test_concurrent_runners_send_once(self):
        with ThreadPoolExecutor(4) as pool:results=list(pool.map(lambda _:self.c.run(self.rid),range(4)))
        self.assertEqual(len(self.client.messages),1);self.assertTrue(all(r==results[0] for r in results))
    def test_second_prompt_is_durable_but_cannot_compete(self):
        with self.assertRaises(TransactionError):self.c.prepare(self.state,'second prompt',self.settings)
        self.assertEqual(self.client.calls,[])
        texts=[json.loads(p.read_text())['text'] for p in self.c.archives.root.glob('*/prompt.json')]
        self.assertIn('second prompt',texts)
        self.assertTrue(self.c.run(self.rid)['old_thread_archived'])
    def test_no_owned_surface(self):
        with self.assertRaises(TransactionError):Coordinator(self.root/'x',self.root/'y',self.client)
    def test_changed_settings_never_forward(self):
        self.client.response['model']='wrong';result=self.c.run(self.rid)
        self.assertEqual(result['state'],'RECOVERY_REQUIRED');self.assertEqual(len(self.client.calls),1)
    def test_nonfresh_never_forward(self):
        self.client.response['thread']['turns']=[{'id':'old'}]
        self.assertEqual(self.c.run(self.rid)['state'],'RECOVERY_REQUIRED');self.assertEqual(len(self.client.calls),1)
    def test_crash_after_forward_acceptance_positive_recovery(self):
        self.c.fault=lambda step:(_ for _ in ()).throw(Crash()) if step=='forward:accepted' else None
        with self.assertRaises(Crash):self.c.run(self.rid)
        self.c.fault=lambda _:None
        self.assertEqual(self.c.run(self.rid)['state'],'RECOVERY_REQUIRED')
        self.assertEqual(reconcile_forward(self.c,self.rid)['state'],'ROLLOVER_ARCHIVING')
        self.assertTrue(self.c.run(self.rid)['old_thread_archived']);self.assertEqual(len(self.client.messages),1)
    def test_absent_readback_never_resends(self):
        self.client.fail='turn/start';self.c.run(self.rid);self.client.fail=None
        self.assertEqual(reconcile_forward(self.c,self.rid)['state'],'RECOVERY_REQUIRED')
        self.c.run(self.rid)
        self.assertEqual(sum(m=='turn/start' for m,p in self.client.calls),1)
        self.assertFalse(any(m=='thread/archive' for m,p in self.client.calls))
    def test_duplicate_readback_does_not_archive(self):
        self.c.fault=lambda step:(_ for _ in ()).throw(Crash()) if step=='forward:accepted' else None
        with self.assertRaises(Crash):self.c.run(self.rid)
        self.c.fault=lambda _:None;self.client.messages*=2
        self.assertEqual(reconcile_forward(self.c,self.rid)['state'],'RECOVERY_REQUIRED')
        self.assertFalse(any(m=='thread/archive' for m,p in self.client.calls))
    def test_archive_positive_readback_then_commit_without_rearchive(self):
        self.c.fault=lambda step:(_ for _ in ()).throw(Crash()) if step=='archive:accepted' else None
        with self.assertRaises(Crash):self.c.run(self.rid)
        self.c.fault=lambda _:None
        request=self.client.request
        self.client.request=lambda m,p: {'data':[{'id':'old','cwd':str(self.root)}],'nextCursor':None} if m=='thread/list' else request(m,p)
        self.assertTrue(reconcile_archive(self.c,self.rid)['archive_confirmed'])
        self.assertTrue(self.c.run(self.rid)['old_thread_archived'])
        self.assertEqual(sum(m=='thread/archive' for m,p in self.client.calls),1)

    def test_damaged_journal_fails_closed(self):
        (self.c.root/self.rid/'prepared.json').write_text('{}')
        with self.assertRaises((KeyError,TransactionError)):self.c.run(self.rid)
        self.assertEqual(self.client.calls,[])
    def test_archive_corruption_never_starts_thread(self):
        (self.c.archives.root/self.rid/'answer.md').write_bytes(b'damaged')
        with self.assertRaises(ValueError):self.c.run(self.rid)
        self.assertEqual(self.client.calls,[])

# Each boundary gets a fresh fixture. BaseException models process death without cleanup code.
def crash_case(boundary):
    def test(self):
        self.c.fault=lambda step:(_ for _ in ()).throw(Crash()) if step==boundary else None
        with self.assertRaises(Crash):self.c.run(self.rid)
        self.c.fault=lambda _:None
        result=self.c.run(self.rid)
        count=lambda method:sum(m==method for m,p in self.client.calls)
        self.assertLessEqual(count('thread/start'),1);self.assertLessEqual(count('turn/start'),1);self.assertLessEqual(count('thread/archive'),1)
        if count('thread/archive'):self.assertTrue((self.c.root/self.rid/'accepted.json').exists())
        self.assertIn(result['state'],{'NORMAL','RECOVERY_REQUIRED'})
        self.assertEqual(json.loads((self.c.archives.root/self.rid/'prompt.json').read_text())['text'],self.prompt)
    return test
for boundary in ['start-intent:durable','start:accepted','started:durable','forward-intent:durable','forward:accepted',
                 'accepted:durable','archive-intent:durable','archive:accepted','archived:durable','committed:durable']:
    setattr(CoordinatorTests,'test_crash_'+boundary.replace(':','_').replace('-','_'),crash_case(boundary))

# A killed process cannot execute Python exception/finally cleanup. Reopen from disk afterward.
def process_crash_case(boundary):
    def test(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,'-m','tests.support.crash_coordinator',str(self.root),self.rid,boundary],cwd=ROOT,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,77,result.stderr.decode())
        previous=[json.loads(s)['method'] for s in (self.root/'child-rpcs.jsonl').read_text().splitlines()] if (self.root/'child-rpcs.jsonl').exists() else []
        outcome=self.c.run(self.rid)
        combined=previous+[m for m,p in self.client.calls]
        for method in ['thread/start','turn/start','thread/archive']:self.assertLessEqual(combined.count(method),1)
        self.assertIn(outcome['state'],{'NORMAL','RECOVERY_REQUIRED'})
    return test
for boundary in ['start-intent:durable','start:accepted','started:durable','forward-intent:durable','forward:accepted',
                 'accepted:durable','archive-intent:durable','archive:accepted','archived:durable','committed:durable']:
    setattr(CoordinatorTests,'test_process_exit_'+boundary.replace(':','_').replace('-','_'),process_crash_case(boundary))
