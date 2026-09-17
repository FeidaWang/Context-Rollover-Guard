import unittest
from crg.advisor import recommend_verified,accepted_workflow_cost


class VerifiedAdvisorTests(unittest.TestCase):
    def test_cheap_model_without_tools_excluded(self):
        capabilities=dict(verified=True,modalities=['text'],tools=['shell'],permission_profiles=['workspace'],context_tokens=1000,approved_risks=['high'])
        catalog=dict(status='VERIFIED_CATALOG',observed_at='2026-01-01T00:00:00Z',models=[
            dict(id='cheap',available=True,reasoning_efforts=['high'],capabilities=capabilities|{'tools':[]}),
            dict(id='capable',available=True,reasoning_efforts=['high'],capabilities=capabilities)])
        policy=dict(candidates=[dict(model_id=model,effort='high',cost_rank=i,capability_rank=i,approved_for=['security']) for i,model in enumerate(('cheap','capable'))])
        req=dict(modalities=['text'],tools=['shell'],permission_profile='workspace',context_tokens=100,risk='high')
        result=recommend_verified(catalog,{'has_security_boundary_change':True},policy,req,at='2026-01-01T00:00:01Z')
        self.assertEqual(result['selected']['model_id'],'capable');self.assertFalse(result['automatic_switch'])
        self.assertIsNone(recommend_verified(catalog,{},policy,req|{'tools':['unavailable']},at='2026-01-01T00:00:01Z')['selected'])

    def test_failed_attempt_cost_is_included(self):
        rows=[dict(task_id='a',accepted=False,quality_source='executed_tests',tokens=100),dict(task_id='b',accepted=True,quality_source='maintainer',tokens=200)]
        self.assertEqual(accepted_workflow_cost(rows)['cost_per_accepted_task']['tokens'],300)
        rows[1]['accepted']=False
        self.assertIsNone(accepted_workflow_cost(rows)['cost_per_accepted_task']['tokens'])
