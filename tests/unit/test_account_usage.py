from datetime import datetime
import unittest
from crg.account import interval, reconcile, unavailable


class AccountTests(unittest.TestCase):
    def test_dst_and_rolling(self):
        a,b=interval('calendar_week',at='2026-10-04T12:00:00Z',timezone_name='Australia/Melbourne')
        self.assertEqual((datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()/3600,167)
        a,b=interval('calendar_week',at='2026-04-05T12:00:00Z',timezone_name='Australia/Melbourne')
        self.assertEqual((datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()/3600,169)
        a,b=interval('rolling_168h',at='2026-10-04T12:00:00Z')
        self.assertEqual((datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()/3600,168)

    def test_null_empty_unknown_and_boundary(self):
        kw=dict(start='2026-09-20T14:00:00Z',end='2026-09-27T14:00:00Z')
        self.assertIsNone(unavailable()['total_tokens'])
        self.assertIsNone(reconcile({},None,**kw)['bucket_count'])
        self.assertEqual(reconcile({},[],provider_timezone='UTC',**kw)['account_total_tokens'],0)
        bucket=[{'date':'2026-09-20','total_tokens':100}]
        self.assertEqual(reconcile({},bucket,**kw)['reconciliation'],'UNKNOWN_BUCKET_TIMEZONE')
        self.assertEqual(reconcile({},bucket,provider_timezone='UTC',**kw)['account_bounds_tokens'],[0,100])
        self.assertFalse(reconcile({},bucket,provider_timezone='UTC',**kw)['additive'])

    def test_public_unsupported_fixture(self):
        import json
        from pathlib import Path
        row=json.loads((Path(__file__).resolve().parents[1]/'fixtures/account/unavailable.json').read_text())
        self.assertIsNone(row['total_tokens']);self.assertEqual(row['status'],'UNSUPPORTED_AUTH_MODE')
