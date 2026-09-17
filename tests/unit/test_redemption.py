from concurrent.futures import ThreadPoolExecutor
import tempfile
from pathlib import Path
import unittest
from crg.redemption import Redemptions


class Adapter:
    contract_id = 'synthetic-contract'
    def __init__(self):
        self.calls = 0
        self.account = 'fixture-account'
        self.receipts = {}
        self.lost = False
        self.readback_fails = False
    def read_state(self):
        if self.calls and self.readback_fails: raise RuntimeError('Readback unavailable')
        return {'account_fingerprint':self.account, 'contract_id':self.contract_id,
                'eligible':True, 'redeemed_intent_id':next(iter(self.receipts), None)}
    def submit(self, *, idempotency_key, approved_effect, approved_cost, expected_account, expected_contract):
        if self.account != expected_account or self.contract_id != expected_contract:
            raise ValueError("Atomic account/contract binding failed")
        self.calls += 1
        receipt = {'intent_id':idempotency_key, 'account_fingerprint':self.account, 'status':'accepted'}
        self.receipts[idempotency_key] = receipt
        if self.lost: raise TimeoutError('Receipt lost after acceptance')
        return receipt
    def lookup(self, key):
        return self.receipts.get(key)


class Redemption(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name).resolve()/'reset.db'
        self.store = Redemptions(self.path)
        self.adapter = Adapter()
        self.intent = self.prepare()
    def tearDown(self):
        self.store.close(); self.tmp.cleanup()
    def prepare(self):
        return self.store.prepare(account_fingerprint='fixture-account', contract_id='synthetic-contract',
            effect='Reset synthetic window', cost='1 synthetic credit',
            at='2026-01-01T00:00:00Z', expires_at='2026-01-01T00:05:00Z')
    def submit(self, **changes):
        args = dict(approved_hash=self.intent['approval_hash'], user_approved=True,
                    adapter=self.adapter, at='2026-01-01T00:01:00Z') | changes
        return self.store.submit(self.intent['intent_id'], **args)
    def test_approval_binds_exact_intent_and_expiry(self):
        for changes in ({'user_approved':False}, {'approved_hash':'wrong'}, {'at':'2026-01-01T00:05:00Z'}):
            with self.assertRaises(ValueError): self.submit(**changes)
        other = self.prepare()
        with self.assertRaises(ValueError): self.submit(approved_hash=other['approval_hash'])
        self.assertEqual(self.adapter.calls, 0)
    def test_acceptance_receipt_readback_and_no_retry(self):
        result = self.submit()
        self.assertEqual(result['state'], 'VERIFIED')
        self.assertTrue(result['readback']['confirmed'])
        self.submit()
        self.assertEqual(self.adapter.calls, 1)
    def test_lost_receipt_reconciles_after_reopen(self):
        self.adapter.lost = True
        with self.assertRaises(TimeoutError): self.submit()
        self.store.close(); self.store = Redemptions(self.path)
        self.assertEqual(self.submit()['state'], 'SUBMITTING')
        result = self.store.reconcile(self.intent['intent_id'], adapter=self.adapter)
        self.assertEqual(result['state'], 'VERIFIED')
        self.assertEqual(self.adapter.calls, 1)
    def test_crash_before_submit_stays_ambiguous(self):
        with self.store.db:
            self.store.db.execute('UPDATE reset_intent SET state="SUBMITTING"')
        self.assertEqual(self.submit()['state'], 'SUBMITTING')
        self.assertEqual(self.store.reconcile(self.intent['intent_id'], adapter=self.adapter)['state'], 'SUBMITTING')
        self.assertEqual(self.adapter.calls, 0)
    def test_readback_failure_keeps_receipt(self):
        self.adapter.readback_fails = True
        with self.assertRaises(RuntimeError): self.submit()
        result = self.submit()
        self.assertEqual(result['state'], 'ACCEPTED')
        self.assertIsNotNone(result['receipt'])
        self.adapter.readback_fails = False
        self.assertEqual(self.store.reconcile(self.intent['intent_id'], adapter=self.adapter)['state'], 'VERIFIED')
        self.assertEqual(self.adapter.calls, 1)
    def test_account_and_contract_change_block(self):
        self.adapter.account = 'other'
        with self.assertRaises(ValueError): self.submit()
        self.adapter.account = 'fixture-account'; self.adapter.contract_id = 'changed'
        with self.assertRaises(ValueError): self.submit()
        self.assertEqual(self.adapter.calls, 0)
    def test_new_intent_cannot_bypass_pending(self):
        self.adapter.lost = True
        with self.assertRaises(TimeoutError): self.submit()
        self.intent = self.prepare()
        with self.assertRaises(ValueError): self.submit()
        self.assertEqual(self.adapter.calls, 1)
    def test_concurrent_claim_submits_at_most_once(self):
        intent = self.intent
        def worker():
            store = Redemptions(self.path)
            try:
                return store.submit(intent['intent_id'], approved_hash=intent['approval_hash'],
                    user_approved=True, adapter=self.adapter, at='2026-01-01T00:01:00Z')['state']
            except ValueError:
                return 'BUSY'
            finally: store.close()
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _:worker(), range(2)))
        self.assertEqual(self.adapter.calls, 1)
    def test_wrong_receipt_keeps_ambiguity(self):
        self.adapter.lost = True
        with self.assertRaises(TimeoutError): self.submit()
        self.adapter.receipts[self.intent['intent_id']]['account_fingerprint'] = 'other'
        with self.assertRaises(ValueError): self.store.reconcile(self.intent['intent_id'], adapter=self.adapter)
        self.assertEqual(self.submit()['state'], 'SUBMITTING')
