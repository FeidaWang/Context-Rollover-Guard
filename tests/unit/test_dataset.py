import json
from pathlib import Path
import re
import unittest
from crg.events import TOKENS,number


class DatasetTests(unittest.TestCase):
    def test_typed_synthetic_dataset_and_chronology(self):
        path=Path(__file__).resolve().parents[2]/'benchmarks/datasets/synthetic-timing-v1.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        allowed={'export_version','bundle_id','record_id','cluster_id','scope','kind','quality','token_unit','time_unit','quota_unit',*TOKENS,'wall_ms','active_ms','acceptance_ms','used_percent','sequence_index'}
        groups={};ids=set()
        for row in rows:
            self.assertEqual(set(row),allowed);self.assertEqual(row['quality'],'synthetic');self.assertEqual(row['kind'],'timing')
            for key in ('record_id','cluster_id','bundle_id'):self.assertRegex(row[key],r'^[0-9a-f]{24}$')
            self.assertNotIn(row['record_id'],ids);ids.add(row['record_id'])
            for key in (*TOKENS,'wall_ms','active_ms','acceptance_ms','used_percent','sequence_index'):number(row[key],integer=key!='used_percent')
            groups.setdefault(row['cluster_id'],[]).append(row['sequence_index'])
        self.assertEqual(len(groups),5);self.assertEqual(len(rows),150)
        self.assertTrue(all(values==list(range(30)) for values in groups.values()))
