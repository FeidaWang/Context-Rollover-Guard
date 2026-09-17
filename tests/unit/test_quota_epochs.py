from pathlib import Path
import tempfile
import unittest
from crg.quota import Quotas


class EpochTests(unittest.TestCase):
    def test_scope_policy_and_unattributed_adjustment(self):
        with tempfile.TemporaryDirectory() as temp:
            q=Quotas(Path(temp).resolve()/'p/db')
            try:
                base=dict(source='synthetic',account_fingerprint='a',bucket_id='short',source_snapshot_id='1',observed_at='2026-09-17T00:00:00Z',used_percent=50,freshness_seconds=60,limit_id='l',policy_epoch='p1')
                old=q.add(base)
                q.add(base|{'source_snapshot_id':'2','observed_at':'2026-09-17T00:00:01Z','used_percent':49})
                current=q.latest('a','short',at='2026-09-17T00:00:02Z',limit_id='l',policy_epoch='p1')
                self.assertEqual(current['epoch_id'],old);self.assertEqual(current['transition'],'UNATTRIBUTED_ADJUSTMENT')
                new=q.add(base|{'policy_epoch':'p2'})
                self.assertNotEqual(old,new)
                self.assertEqual(q.latest('a','short',at='2026-09-17T00:00:02Z',limit_id='l',policy_epoch='p1')['epoch_id'],old)
            finally:q.close()
