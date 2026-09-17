from pathlib import Path
import tempfile,unittest
from crg.quota import Quotas

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.q=Quotas(Path(self.temp.name).resolve()/'private/ledger.sqlite');self.addCleanup(self.q.close)
    def row(self,i,used,**kwargs):
        return dict(source='synthetic official snapshot',account_fingerprint='fixture-account',bucket_id='weekly',
            source_snapshot_id=str(i),observed_at=f'2026-09-17T0{i}:00:00Z',used_percent=used,
            reset_at='2026-09-17T01:30:00Z',freshness_seconds=3600,**kwargs)
    def test_reset_timezone_replay_and_history(self):
        first=self.q.add(self.row(1,90));self.assertEqual(first,self.q.add(self.row(1,90)))
        second=self.q.add(self.row(2,5)|{'observed_at':'2026-09-17T12:00:00+10:00'})
        self.assertNotEqual(first,second)
        self.assertEqual(self.q.db.execute('SELECT count(*) FROM quota_snapshot').fetchone()[0],2)
        report=self.q.latest('fixture-account','weekly',at='2026-09-17T02:30:00Z')
        self.assertEqual(report['remaining_percent'],95);self.assertIsNone(report['tokens_remaining'])
        self.assertIsNone(self.q.latest('fixture-account','weekly',at='2026-09-18T00:00:00Z')['remaining_percent'])
    def test_accounts_buckets_and_no_reset_from_drop_alone(self):
        first=self.q.add(self.row(1,90)|{'reset_at':None})
        second=self.q.add(self.row(2,5));self.assertEqual(first,second)
        self.assertNotEqual(first,self.q.add(self.row(3,5)|{'bucket_id':'five-hour'}))
        self.assertNotEqual(first,self.q.add(self.row(3,5)|{'account_fingerprint':'second'}))
    def test_explicit_reset_and_unknown(self):
        first=self.q.add(self.row(1,None))
        second=self.q.add(self.row(2,None,user_confirmed_reset=True))
        self.assertNotEqual(first,second)
        self.assertIsNone(self.q.latest('absent','weekly',at='2026-09-18T00:00:00Z')['remaining_percent'])
        with self.assertRaises(ValueError):self.q.add(self.row(3,101))
