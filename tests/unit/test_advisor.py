import unittest
from crg.advisor import recommend

class AdviceTests(unittest.TestCase):
    def catalog(self):return {'status':'VERIFIED_CATALOG','observed_at':'2026-09-17T00:00:00Z','models':[
        {'id':'small','available':True,'reasoning_efforts':['custom']},
        {'id':'large','available':True,'reasoning_efforts':['custom']} ]}
    def policy(self):return {'candidates':[{'model_id':name,'effort':'custom','cost_rank':rank,'capability_rank':rank,'approved_for':['security']} for name,rank in [('small',1),('large',2)]]}
    def advise(self,features,**kwargs):return recommend(self.catalog(),features,self.policy(),at='2026-09-17T00:10:00Z',**kwargs)
    def test_cold_security_floor_and_docs_cost(self):
        self.assertEqual(self.advise({'has_security_boundary_change':True})['selected']['model_id'],'large')
        self.assertEqual(self.advise({'is_docs_only':True})['selected']['model_id'],'small')
    def test_unavailable_efforts_and_stale_catalog(self):
        policy=self.policy();policy['candidates'][0]['effort']='invented'
        self.assertEqual(recommend(self.catalog(),{},policy,at='2026-09-17T00:00:00Z')['selected']['model_id'],'large')
        self.assertIsNone(recommend(self.catalog(),{},policy,at='2026-09-18T00:00:00Z')['selected'])
    def test_quality_gate_and_no_unsafe_guess(self):
        self.assertEqual(self.advise({},history={'small|custom':{'sample_count':20,'successes':3,'observed_at':'2026-09-17T00:00:00Z'}})['selected']['model_id'],'large')
        self.assertIsNone(self.advise({'has_protocol_change':True})['selected'])
