from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import unittest
import tempfile
from pathlib import Path
from tests.support.model_registry import contract
from crg.models import normalize_model, resolve_action


class ModelResolution(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.schema,self.binding,self.params=contract(Path(temp.name).resolve())
        self.at = datetime.now(timezone.utc).isoformat()
        self.catalog = {'status':'VERIFIED_CATALOG', 'observed_at':self.at, 'source':'synthetic', 'binding':self.binding,
            'models':[asdict(normalize_model({'id':'unfamiliar-fixture-id',
                'supportedReasoningEfforts':['custom']}, observed_at=self.at))]}
    def resolve(self, **changes):
        return resolve_action(self.catalog, **(dict(model_id='unfamiliar-fixture-id', effort='custom', at=self.at, schema=self.schema, binding=self.binding,
                    authorized_params=self.params, permission_profile=':read-only') | changes))
    def test_explicit_new_id_without_static_assumptions(self):
        result = self.resolve()
        self.assertEqual(result['status'], 'RESOLVED')
        self.assertIsNone(result['capabilities']['context_window'])
        self.assertIsNone(result['capabilities']['family'])
        self.assertFalse(result['automatic_switch'])
    def test_unknown_id_effort_stale_and_duplicate(self):
        for args in ({'model_id':'guessed'}, {'effort':'high'}, {'at':'2026-01-01T02:00:00Z'}):
            self.assertEqual(self.resolve(**args)['status'], 'UNAVAILABLE')
        self.catalog['models'] *= 2
        self.assertEqual(self.resolve()['status'], 'UNAVAILABLE')
    def test_revision_change_requires_new_decision(self):
        previous = self.resolve()['capability_revision']
        self.catalog['models'][0]['context_window'] = 12345
        result = self.resolve(expected_revision=previous)
        self.assertEqual(result['reason'], 'CAPABILITIES_CHANGED')
        self.assertTrue(result['reset_estimator'])
        self.assertEqual(self.resolve(expected_revision=result['capability_revision'])['status'], 'RESOLVED')
    def test_observation_time_not_a_capability_change(self):
        previous = self.resolve()['capability_revision']
        self.catalog['observed_at'] = (datetime.fromisoformat(self.at)-timedelta(minutes=1)).isoformat()
        self.assertEqual(self.resolve(expected_revision=previous)['status'], 'RESOLVED')

    def test_malformed_effort_list_is_not_substring_matching(self):
        self.catalog['models'][0]['reasoning_efforts'] = 'custom'
        self.assertEqual(self.resolve(effort='cust')['status'], 'UNAVAILABLE')
