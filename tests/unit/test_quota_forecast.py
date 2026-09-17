import unittest
from crg.quota_forecast import capacity


class CapacityTests(unittest.TestCase):
    def inputs(self):
        buckets=[dict(bucket_id=b,epoch_id='e',status='OBSERVED',remaining_percent=r,resolution_percent=1,reset_at='2026-01-02T00:00:00Z') for b,r in [('short',40),('long',20)]]
        samples=[dict(task_id=str(i),bucket_id=b,policy_hash='p',start_epoch='e',end_epoch='e',complete=True,external_activity=False,used_percent=3,completed_at='2025-12-31T00:00:00Z') for b in ('short','long') for i in range(5)]
        return buckets,samples

    def test_limiting_bucket_and_incomplete(self):
        b,s=self.inputs();kw=dict(policy_hash='p',at='2026-01-01T00:00:00Z',coverage_complete=True)
        result=capacity(b,s,**kw)
        self.assertEqual((result['comparable_tasks'],result['limiting_bucket']),(3,'long'))
        self.assertIsNone(result['tokens_remaining'])
        self.assertIsNone(capacity(b,s,**(kw|{'coverage_complete':False}))['comparable_tasks'])
        self.assertIsNone(capacity(b,s,**(kw|{'policy_hash':'new'}))['comparable_tasks'])
        for row in s:row['used_percent']=0
        self.assertEqual(capacity(b,s,**kw)['reason'],'BELOW_PERCENTAGE_RESOLUTION')

    def test_cross_epoch_and_external_activity(self):
        b,s=self.inputs()
        for row in s:row['end_epoch']='different'
        self.assertIsNone(capacity(b,s,policy_hash='p',at='2026-01-01T00:00:00Z',coverage_complete=True)['comparable_tasks'])
