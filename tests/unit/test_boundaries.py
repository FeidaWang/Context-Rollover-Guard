import json
from pathlib import Path
import tempfile
import unittest

from crg.boundaries import inventory
from crg.calibration import summarize


class BoundaryInventoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.path = self.root / 'native.jsonl'
        self.rows = [
            {'type': 'session_meta', 'payload': {'id': 's', 'cli_version': 'v1'}},
            {'type': 'turn_context', 'payload': {'turn_id': 't', 'model': 'm', 'cwd': str(self.root)}},
            {'type': 'token_usage_record', 'payload': {'thread_id': 's', 'turn_id': 't',
                'usage': {'total_tokens': 123}, 'thread_token_usage': {'total_tokens': 99999}}},
            {'type': 'compacted', 'payload': {'text': 'PRIVATE ANSWER'}}]

    def write(self):
        self.path.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))

    def scan(self):
        self.write()
        return inventory([self.path], workspace=self.root)

    def test_active_is_not_cumulative_or_threshold(self):
        result = self.scan()
        row = result['observations'][0]
        self.assertEqual(row['preceding_active_context_tokens'], 123)
        self.assertIsNone(row['observed_compact_limit'])
        self.assertEqual(summarize(result['observations']), [])
        self.assertNotIn('PRIVATE ANSWER', json.dumps(result))

    def test_copies_and_repeated_paths_do_not_duplicate(self):
        self.write()
        copy = self.root / 'copy.jsonl'
        copy.write_bytes(self.path.read_bytes())
        result = inventory([self.path, self.path, copy], workspace=self.root)
        self.assertEqual(len(result['observations']), 1)
        self.assertEqual(result['files_scanned'], 2)

    def test_conflicting_copy_rejected(self):
        self.write()
        copy = self.root / 'copy.jsonl'
        copy.write_text(self.path.read_text().replace('123', '124'))
        with self.assertRaises(ValueError):
            inventory([self.path, copy], workspace=self.root)

    def test_foreign_workspace_and_turn_cannot_supply_usage(self):
        self.rows[2]['payload']['turn_id'] = 'foreign'
        self.assertIsNone(self.scan()['observations'][0]['preceding_active_context_tokens'])
        self.rows[1]['payload']['cwd'] = str(self.root / 'other')
        self.assertEqual(self.scan()['observations'], [])

    def test_boundary_clears_usage(self):
        self.rows.append(self.rows[-1])
        values = [r['preceding_active_context_tokens'] for r in self.scan()['observations']]
        self.assertCountEqual(values, [123, None])

    def test_new_turn_cannot_reuse_old_binding(self):
        self.rows.insert(3, {'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 'other'}})
        self.assertEqual(self.scan()['observations'], [])

    def test_incomplete_tail_and_malformed_complete_record(self):
        self.write()
        with self.path.open('a') as stream:
            stream.write('{"private":')
        self.assertEqual(inventory([self.path], workspace=self.root)['incomplete_tails_ignored'], 1)
        with self.path.open('a') as stream:
            stream.write('\n')
        with self.assertRaisesRegex(ValueError, 'Malformed complete'):
            inventory([self.path], workspace=self.root)

    def test_symlink_and_missing_identity_rejected(self):
        self.write()
        link = self.root / 'link'
        link.symlink_to(self.path)
        with self.assertRaises(OSError):
            inventory([link], workspace=self.root)
        self.rows.pop(0)
        with self.assertRaises(ValueError):
            self.scan()

    def test_runtime_model_groups_remain_separate(self):
        # Version-like substrings in temporary paths must not change the binding.
        self.root = self.root / 'v1-workspace'
        self.root.mkdir()
        self.path = self.root / 'native.jsonl'
        self.rows[1]['payload']['cwd'] = str(self.root)
        self.write()
        copy = self.root / 'second.jsonl'
        rows = [json.loads(line) for line in self.path.read_text().splitlines()]
        rows[0]['payload'].update(id='s2', cli_version='v2')
        rows[2]['payload']['thread_id'] = 's2'
        copy.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        self.assertEqual(len(inventory([self.path, copy], workspace=self.root)['groups']), 2)
