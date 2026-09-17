import json,unittest
from tests.unit import test_owned_client
from crg.owned_recovery import reconcile_run


class RecoveryTests(unittest.TestCase):
    setUp=test_owned_client.OwnedTests.setUp
    def prepare_lost_completion(self):
        output=self.session.submit(' exact\r\n🙂 ', fresh=True)
        (self.session.root/'input-000001-completed.json').unlink()
        intent=json.loads((self.session.root/'input-000001-intent.json').read_text())
        self.native={'thread':{'id':self.session.thread,'cwd':str(self.root),'turns':[{
            'id':output['turn_id'],'status':'completed','items':[
                {'type':'userMessage','clientId':intent['clientUserMessageId'],'content':intent['input']},
                {'type':'agentMessage','phase':'final_answer','text':output['text']}]}]}}
        self.reads=[]
        def request(method,params):
            self.assertEqual(method,'thread/read');self.reads.append(params);return self.native
        self.client.request=request
    def test_positive_completion_restores_receipt_without_resend(self):
        self.prepare_lost_completion()
        self.assertEqual(reconcile_run(self.session.root,self.client,self.config)['state'],'READY_TO_RESUME')
        self.assertEqual(len(self.reads),1)
        self.assertTrue((self.session.root/'input-000001-completed.json').exists())
        self.assertEqual(reconcile_run(self.session.root,self.client,self.config)['state'],'READY_TO_RESUME')
        self.assertEqual(len(self.reads),1)
    def test_duplicate_acceptance_refused(self):
        self.prepare_lost_completion();items=self.native['thread']['turns'][0]['items'];items.append(items[0])
        self.assertEqual(reconcile_run(self.session.root,self.client,self.config)['reason'],'ACCEPTANCE_ABSENT_OR_DUPLICATED')
        self.assertFalse((self.session.root/'input-000001-completed.json').exists())
    def test_changed_answer_refused(self):
        self.prepare_lost_completion();self.native['thread']['turns'][0]['items'][1]['text']='different'
        self.assertEqual(reconcile_run(self.session.root,self.client,self.config)['reason'],'FINAL_ANSWER_MISMATCH_OR_UNAVAILABLE')
    def test_in_progress_refused(self):
        self.prepare_lost_completion();self.native['thread']['turns'][0]['status']='inProgress'
        self.assertEqual(reconcile_run(self.session.root,self.client,self.config)['reason'],'TURN_NOT_COMPLETED')
    def test_changed_prompt_refused(self):
        self.prepare_lost_completion();self.native['thread']['turns'][0]['items'][0]['content'][0]['text']='changed'
        self.assertEqual(reconcile_run(self.session.root,self.client,self.config)['reason'],'CONTENT_MISMATCH')
