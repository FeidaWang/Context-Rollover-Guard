from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from crg.forecast import Forecasts
from crg.features import features
from tests.unit.test_features import POLICY,INTENT


def stamp(i):return (datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(seconds=i)).isoformat()


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Forecasts(Path(self.tmp.name).resolve()/'p/db');self.addCleanup(self.f.close)

    def predict(self,i,**change):
        return self.f.predict(features(INTENT|{'task_id':str(i)}|change,POLICY,at=stamp(i*10)))

    def test_prequential_future_leakage_and_revision(self):
        predictions=[]
        for i in range(6):
            p=self.predict(i);predictions.append(p)
            self.f.complete(p['id'],at=stamp(i*10+1),status='completed',value=100)
        self.assertIsNone(predictions[0]['interval']);self.assertEqual(predictions[-1]['median'],100)
        before=self.predict(7)
        self.f.complete(predictions[0]['id'],revision=1,at=stamp(100),status='completed',value=999999)
        # A query earlier than revision arrival must not see the correction.
        self.assertEqual(self.predict(8)['median'],100)
        self.assertEqual(self.f.predict(before['features']),before)
        with self.assertRaises(ValueError):self.f.complete(before['id'],at=stamp(0),status='completed',value=1)
        self.assertEqual(self.predict(11)['sample_count'],6)

    def test_cancelled_unknown_and_duplicate(self):
        p=self.predict(0)
        for _ in range(10):self.f.complete(p['id'],at=stamp(1),status='cancelled',value=50)
        q=self.predict(1)
        self.assertEqual(q['sample_count'],0);self.assertEqual(q['censoring_rate'],1)
        with self.assertRaises(ValueError):self.f.complete(p['id'],at=stamp(1),status='completed',value=1)

    def test_model_regime_and_feature_range(self):
        for i in range(11):
            p=self.predict(i);self.f.complete(p['id'],at=stamp(i*10+1),status='completed',value=0)
        self.assertEqual(self.predict(12,input_bytes=99999)['status'],'FEATURE_RANGE_FALLBACK')
        p=self.f.predict(features(INTENT|{'task_id':'new'},POLICY|{'runtime_version':'new'},at=stamp(200)))
        self.assertIsNone(p['interval'])
