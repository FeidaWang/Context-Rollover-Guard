import tempfile,unittest
from pathlib import Path
from crg.estimates import Estimates

class EstimateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.e=Estimates(Path(self.temp.name).resolve()/'private/data.sqlite');self.addCleanup(self.e.close)
    def record(self,i,status='completed'):
        p=self.e.begin('code','m','custom','v',prediction_id=str(i),at=f'2026-09-17T00:{i:02d}:00Z')
        self.e.complete(p['prediction_id'],status=status,duration_ms=1000+i*100,total_tokens=10,
            success=True if status=='completed' else None,at=f'2026-09-17T00:{i:02d}:30Z')
        return p
    def test_pre_result_censoring_and_backoff(self):
        first=self.record(0);self.assertIsNone(first['duration_interval_ms'])
        for i in range(1,5):self.record(i)
        self.record(5,'timeout')
        p=self.e.begin('code','other','custom','v',at='2026-09-17T01:00:00Z')
        self.assertEqual(p['sample_count'],5);self.assertEqual(p['scope'],'task')
        self.assertIsNotNone(p['duration_interval_ms'])
        self.assertEqual(self.e.quality_history(at='2026-09-17T01:00:00Z',runtime_version='v')['m|custom']['sample_count'],5)
    def test_runtime_change_staleness_and_order(self):
        for i in range(5):self.record(i)
        for version,at in [('changed','2026-09-17T01:00:00Z'),('v','2026-11-17T01:00:00Z')]:
            self.assertIsNone(self.e.begin('code','m','custom',version,at=at)['duration_interval_ms'])
        with self.assertRaises(ValueError):self.e.complete('missing',status='completed',duration_ms=10)
        with self.assertRaises(ValueError):self.e.complete('0',status='completed',duration_ms=10,at='2020-01-01T00:00:00Z')
    def test_prediction_is_immutable_on_reopen(self):
        first=self.e.begin('code','m','custom','v',prediction_id='p',at='2026-09-17T00:00:00Z')
        self.assertEqual(first,self.e.begin('code','m','custom','v',prediction_id='p'))
        with self.assertRaises(ValueError):self.e.begin('different','m','custom','v',prediction_id='p')

    def test_drift_widens_intervals_and_scores_saved_prediction(self):
        for i in range(5):self.record(i)
        forecast=self.e.begin('code','m','custom','v',prediction_id='score',at='2026-09-17T00:06:00Z')
        self.e.complete('score',status='completed',duration_ms=1000000,at='2026-09-17T00:06:30Z')
        import json
        score=json.loads(self.e.db.execute('SELECT score FROM task_observation WHERE prediction_id=?',('score',)).fetchone()[0])
        self.assertFalse(score['duration_interval_hit'])
        for i in range(7,11):
            p=self.e.begin('code','m','custom','v',at=f'2026-09-17T00:{i:02d}:00Z')
            self.e.complete(p['prediction_id'],status='completed',duration_ms=1000000,at=f'2026-09-17T00:{i:02d}:30Z')
        next_prediction=self.e.begin('code','m','custom','v',at='2026-09-17T01:00:00Z')
        self.assertTrue(next_prediction['drift_detected'])
        self.assertEqual(next_prediction['duration_interval_ms'][1],2000000)
