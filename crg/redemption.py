"""Durable reset transaction engine for explicitly supplied, verified adapters.

No production adapter or CLI submission command is shipped. Adapter verification
and collection of a fresh human approval are responsibilities of the host UI.
"""
from datetime import datetime
import json
import uuid

from .ledger import connect, identity, timestamp


class Redemptions:
    def __init__(self, path):
        self.db = connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS reset_intent(intent_id TEXT PRIMARY KEY, payload TEXT NOT NULL, approval_hash TEXT NOT NULL, state TEXT NOT NULL, receipt TEXT, readback TEXT)')
        self.db.commit()

    def close(self):
        self.db.close()

    def get(self, intent_id):
        row = self.db.execute('SELECT * FROM reset_intent WHERE intent_id=?', (intent_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown reset intent')
        return {**dict(row), 'payload': json.loads(row['payload']),
                'receipt': json.loads(row['receipt']) if row['receipt'] else None,
                'readback': json.loads(row['readback']) if row['readback'] else None}

    def prepare(self, *, account_fingerprint, contract_id, effect, cost, at, expires_at):
        for value in (account_fingerprint, contract_id, effect, cost):
            if not isinstance(value, str) or not value.strip():
                raise ValueError('Exact account, verified contract, effect and cost required')
        created, expires = timestamp(at), timestamp(expires_at)
        seconds = (datetime.fromisoformat(expires)-datetime.fromisoformat(created)).total_seconds()
        if not 0 < seconds <= 300:
            raise ValueError('Approval intent expires within five minutes')
        payload = {'intent_id': str(uuid.uuid4()), 'account_fingerprint': account_fingerprint,
                   'contract_id': contract_id, 'effect': effect, 'cost': cost,
                   'created_at': created, 'expires_at': expires}
        encoded = json.dumps(payload, sort_keys=True)
        with self.db:
            self.db.execute('INSERT INTO reset_intent VALUES(?,?,?,"PREPARED",NULL,NULL)',
                            (payload['intent_id'], encoded, identity(payload)))
        return self.get(payload['intent_id'])

    def submit(self, intent_id, *, approved_hash, user_approved, adapter, at):
        """Claim once before any mutation; a crash leaves an ambiguous, non-retriable intent."""
        intent = self.get(intent_id)
        if intent['state'] != 'PREPARED':
            return intent  # Every subsequent path is read-only reconciliation.
        payload = intent['payload']
        current = timestamp(at)
        if (user_approved is not True or approved_hash != intent['approval_hash']
                or not payload['created_at'] <= current < payload['expires_at']):
            raise ValueError('Fresh explicit approval of this exact effect and cost required')
        if adapter.contract_id != payload['contract_id']:
            raise ValueError('Verified adapter contract changed')
        before = adapter.read_state()
        if (before.get('account_fingerprint') != payload['account_fingerprint']
                or before.get('contract_id') != payload['contract_id'] or before.get('eligible') is not True):
            raise ValueError('Fresh same-account eligibility is required')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            # A different in-flight intent for this account also blocks submission.
            for other in self.db.execute('SELECT payload FROM reset_intent WHERE state IN ("SUBMITTING","ACCEPTED")'):
                if json.loads(other[0])['account_fingerprint'] == payload['account_fingerprint']:
                    raise ValueError('Reconcile the existing account intent first')
            changed = self.db.execute('UPDATE reset_intent SET state="SUBMITTING" WHERE intent_id=? AND state="PREPARED"', (intent_id,)).rowcount
        if not changed:
            return self.get(intent_id)
        # Exceptions deliberately leave SUBMITTING durable. Never call submit again.
        receipt = adapter.submit(idempotency_key=intent_id, approved_effect=payload['effect'],
                                 approved_cost=payload['cost'],
                                 expected_account=payload['account_fingerprint'],
                                 expected_contract=payload['contract_id'])
        self._receipt(intent_id, receipt)
        return self.reconcile(intent_id, adapter=adapter)

    def _receipt(self, intent_id, receipt):
        intent = self.get(intent_id)
        if (not isinstance(receipt, dict) or receipt.get('intent_id') != intent_id
                or receipt.get('account_fingerprint') != intent['payload']['account_fingerprint']
                or receipt.get('status') not in {'accepted', 'already_redeemed', 'no_credit', 'nothing_to_reset', 'ineligible'}):
            raise ValueError('Ambiguous or mismatched receipt; reconcile without resubmitting')
        projected = {key: receipt[key] for key in ('intent_id', 'account_fingerprint', 'status')}
        encoded = json.dumps(projected, sort_keys=True)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old = self.get(intent_id)
            if old['receipt'] is not None and old['receipt'] != projected:
                raise ValueError('Conflicting reset receipt')
            if old['state'] == 'SUBMITTING':
                self.db.execute('UPDATE reset_intent SET receipt=?,state=? WHERE intent_id=?',
                    (encoded, 'ACCEPTED' if projected['status'] in {'accepted','already_redeemed'} else 'DECLINED', intent_id))

    def cancel(self, intent_id):
        """Cancel only before dispatch; uncertainty must remain reconcilable."""
        with self.db:
            self.db.execute('UPDATE reset_intent SET state="CANCELLED" WHERE intent_id=? AND state="PREPARED"', (intent_id,))
        return self.get(intent_id)

    def reconcile(self, intent_id, *, adapter):
        intent = self.get(intent_id)
        if adapter.contract_id != intent['payload']['contract_id']:
            raise ValueError('Verified adapter contract changed')
        if intent['state'] == 'SUBMITTING':
            # Only authoritative keyed lookup is admissible, never a quota percentage drop.
            receipt = adapter.lookup(intent_id)
            if receipt is None:
                return intent
            self._receipt(intent_id, receipt)
            intent = self.get(intent_id)
        if intent['state'] == 'ACCEPTED':
            snapshot = adapter.read_state()
            if (snapshot.get('account_fingerprint') != intent['payload']['account_fingerprint']
                    or snapshot.get('contract_id') != intent['payload']['contract_id']
                    or snapshot.get('redeemed_intent_id') != intent_id):
                return intent
            # Store only a confirmation marker; raw account data is never persisted.
            readback = json.dumps({'intent_id': intent_id, 'confirmed': True,
                                   'changed_buckets': None, 'all_windows_reset': None})
            with self.db:
                self.db.execute('UPDATE reset_intent SET readback=?,state="VERIFIED" WHERE intent_id=? AND state="ACCEPTED"',
                                (readback, intent_id))
        return self.get(intent_id)
