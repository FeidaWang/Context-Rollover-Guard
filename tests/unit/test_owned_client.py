import tempfile,unittest
from pathlib import Path
from dataclasses import replace
from tests.unit.test_coordinator import FakeClient
from crg.owned_client import OwnedSession
from crg.config import Config,General
from crg.domain import SessionState,State
from crg.state_store import StateStore
from crg.hooks import HookDispatcher


class NativeFake(FakeClient):
    def __init__(self,root,config):
        super().__init__(root);self.config=config;self.events=[];self.starts=0;self.turns=0
    def request(self,method,params):
        if method=='thread/resume':
            return dict(self.response,thread={'id':params['threadId'],'cwd':str(self.workspace),'turns':[]})
        if method=='thread/start':
            self.starts+=1;self.response['thread']['id']='thread-'+str(self.starts)
        result=super().request(method,params)
        if method=='turn/start':
            self.turns+=1;turn='turn-'+str(self.turns);result['turn']['id']=turn
            tid=params['threadId'];store=StateStore(self.config.paths(self.workspace)[1],self.workspace,tid)
            store.update(lambda s:s,initial=replace(SessionState.create(self.workspace,tid,tid),mode='MODE_B'))
            HookDispatcher(store,self.config).stop({'session_id':tid,'cwd':str(self.workspace),'turn_id':turn,'last_assistant_message':'answer '+turn})
            self.events.append({'method':'turn/completed','params':{'threadId':tid,'turn':{'id':turn,'status':'completed'}}})
        return result
    def next_event(self,timeout):return self.events.pop(0) if self.events else None


class OwnedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.config=Config(context_rollover=General(enabled=True,mode='MODE_B',state_root=str(self.root/'states'),archive_root=str(self.root/'archives')))
        self.client=NativeFake(self.root,self.config);self.session=OwnedSession(self.client,self.config,timeout=.02)
        self.session.start({'sandbox':'read-only'})
    def test_consecutive_turns_route_after_rollover(self):
        first=self.session.submit('first');old=self.session.thread
        store=StateStore(self.config.paths(self.root)[1],self.root,old)
        store.update(lambda s:replace(s,state=State.ARMED.value))
        second=self.session.submit(' exact\r\n🙂 ');new=self.session.thread
        third=self.session.submit('third')
        self.assertNotEqual(old,new);self.assertEqual(third['thread_id'],new)
        calls=[p for m,p in self.client.calls if m=='turn/start']
        self.assertEqual([p['threadId'] for p in calls],[old,new,new])
        self.assertEqual(calls[1]['input'][0]['text'],' exact\r\n🙂 ')
        self.assertEqual([p['threadId'] for m,p in self.client.calls if m=='thread/archive'],[old])
    def test_unknown_acceptance_blocks_followup_and_keeps_prompt(self):
        self.client.fail='turn/start'
        with self.assertRaises(RuntimeError):self.session.submit('keep me')
        before=len(self.client.calls)
        with self.assertRaises(ValueError):self.session.submit('do not send')
        self.assertEqual(before,len(self.client.calls))
        self.assertIn('keep me',(self.session.root/'input-000001.json').read_text())
    def test_missing_native_stop_blocks_further_inputs(self):
        self.client.next_event=lambda timeout:{'method':'turn/completed','params':{'threadId':self.session.thread,'turn':{'id':'turn-1','status':'failed'}}}
        with self.assertRaises(RuntimeError):self.session.submit('x')
        self.assertTrue(self.session.blocked)

    def test_resume_follows_last_completed_route(self):
        self.session.submit('first')
        store=StateStore(self.config.paths(self.root)[1],self.root,self.session.thread)
        store.update(lambda s:replace(s,state=State.ARMED.value))
        self.session.submit('second');new=self.session.thread
        resumed=OwnedSession(self.client,self.config,timeout=.02)
        resumed.resume(self.session.root)
        self.assertEqual(resumed.thread,new)
        self.assertEqual(resumed.submit('third')['thread_id'],new)
    def test_resume_refuses_unknown_input_without_rpc(self):
        self.client.fail='turn/start'
        with self.assertRaises(RuntimeError):self.session.submit('durable')
        before=len(self.client.calls)
        resumed=OwnedSession(self.client,self.config,timeout=.02)
        with self.assertRaises(ValueError):resumed.resume(self.session.root)
        self.assertEqual(len(self.client.calls),before)
