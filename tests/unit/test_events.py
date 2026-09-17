import unittest
from crg.events import Observation, project


def usage(i=1, total=100, **changes):
    row = dict(schema_version=1, kind='usage', observation_id=str(i), fact_id=str(i),
               revision=0, source='fixture', adapter_version='1', scope='local',
               account_id='a', workspace_id='w', thread_id='t', quality='synthetic',
               observed_at=f'2026-09-17T00:00:{i:02d}Z', received_at='2026-09-18T00:00:00Z',
               data=dict(total_tokens=total, semantics='cumulative_snapshot', generation='g',
                         aggregation='exclusive', subset_contract='unknown'))
    row.update(changes)
    return row


class EventsTests(unittest.TestCase):
    def test_null_zero_and_invalid(self):
        for total in (None, 0, 100):
            self.assertEqual(Observation(usage(total=total)).exact_usage(), total)
        for total in (-1, True, float('nan'), float('inf')):
            with self.assertRaises(ValueError): Observation(usage(total=total))

    def test_semantic_objects_and_projection(self):
        with self.assertRaises(ValueError): Observation(usage(kind='context'))
        row = usage(); row['prompt'] = 'private'; row['data']['answer'] = 'private'
        self.assertNotIn('private', str(project(row).to_dict()))
        with self.assertRaises(ValueError): Observation(row)
        self.assertIsNone(Observation(usage(scope='unknown')).exact_usage())

    def test_subsets_and_parent(self):
        row = usage(); row['data'].update(input_tokens=80, output_tokens=20,
            cached_input_tokens=50, reasoning_output_tokens=10,
            subset_contract='input_output_include_subsets')
        self.assertEqual(Observation(row).exact_usage(), 100)
        row['data']['parent_id'] = 'parent'
        self.assertIsNone(Observation(row).exact_usage())
        row['data']['cached_input_tokens'] = 81
        with self.assertRaises(ValueError): Observation(row)

    def test_public_contract_fixture(self):
        import json
        from pathlib import Path
        rows=json.loads((Path(__file__).resolve().parents[1]/'fixtures/usage/contracts.json').read_text())['cases']
        for i,row in enumerate(rows):
            if i in (2,3):
                with self.assertRaises(ValueError):Observation(row)
            else:Observation(row)
