import unittest
from scripts.benchmark_continuity import scenario

class BenchmarkTests(unittest.TestCase):
    def test_all_defined_protocol_paths(self):
        for path in ('native','observe','handoff','recovery'):
            with self.subTest(path=path):
                row=scenario(path)
                self.assertTrue(row['protocol_correct'])
                self.assertEqual(row['duplicate_mutations'],0)
                self.assertTrue(row['source_retained'])
