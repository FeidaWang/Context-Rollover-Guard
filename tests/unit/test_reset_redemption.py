from pathlib import Path
import tempfile
import unittest
from crg.redemption import Redemptions
from tests.unit.test_redemption import Adapter


class ResetExtensionTests(unittest.TestCase):
    def test_cancel_and_declined_outcomes(self):
        for outcome in ('no_credit','nothing_to_reset','already_redeemed'):
            with self.subTest(outcome=outcome),tempfile.TemporaryDirectory() as temp:
                db=Redemptions(Path(temp).resolve()/'db');adapter=Adapter()
                try:
                    def prepare():return db.prepare(account_fingerprint='fixture-account',contract_id=adapter.contract_id,effect='synthetic short bucket',cost='one synthetic credit',at='2026-01-01T00:00:00Z',expires_at='2026-01-01T00:05:00Z')
                    cancelled=prepare();db.cancel(cancelled['intent_id'])
                    self.assertEqual(db.submit(cancelled['intent_id'],approved_hash=cancelled['approval_hash'],user_approved=True,adapter=adapter,at='2026-01-01T00:01:00Z')['state'],'CANCELLED')
                    self.assertEqual(adapter.calls,0)
                    original=adapter.submit
                    def submit(**kw):
                        receipt=original(**kw);receipt['status']=outcome;return receipt
                    adapter.submit=submit
                    intent=prepare()
                    result=db.submit(intent['intent_id'],approved_hash=intent['approval_hash'],user_approved=True,adapter=adapter,at='2026-01-01T00:01:00Z')
                    self.assertEqual(result['state'],'VERIFIED' if outcome=='already_redeemed' else 'DECLINED')
                    if result['state']=='VERIFIED':self.assertIsNone(result['readback']['changed_buckets'])
                    self.assertEqual(adapter.calls,1)
                finally:db.close()
