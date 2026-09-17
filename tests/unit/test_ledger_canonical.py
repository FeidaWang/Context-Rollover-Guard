from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from crg.ledger import CanonicalLedger
from tests.unit.test_events import usage


class CanonicalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name).resolve() / 'private/ledger.sqlite'
        self.ledger = CanonicalLedger(self.path); self.addCleanup(self.ledger.close)

    def result(self):
        return self.ledger.usage('local', '2026-09-17T00:00:00Z', '2026-09-18T00:00:00Z')

    def test_ten_replays_out_of_order_and_revision(self):
        for _ in range(10): self.ledger.ingest([usage(3, 130), usage(1, 100), usage(2, 130)])
        self.assertEqual((self.result()['known_total_tokens'], self.result()['sample_count']), (30, 3))
        self.ledger.ingest([usage(2, 120, revision=1)])
        self.assertEqual(self.result()['known_total_tokens'], 30)
        self.assertEqual(self.ledger.db.execute('SELECT count(*) FROM observation').fetchone()[0], 4)
        with self.assertRaises(ValueError): self.ledger.ingest([usage(2, 121, revision=1)])

    def test_generation_and_unknown_baseline(self):
        row = usage(3, 500); row['data']['generation'] = 'new'
        self.ledger.ingest([usage(1, 100), usage(2, 130), row])
        self.assertEqual(self.result()['known_total_tokens'], 30)
        self.assertEqual(self.result()['unknown_samples'], 2)

    def test_cursor_compare_swap_and_fault(self):
        def fail(stage):
            if stage == 'before_commit': raise RuntimeError('injected')
        with self.assertRaises(RuntimeError):
            self.ledger.ingest([usage()], source='s', cursor={'offset': 1}, fault=fail)
        self.assertIsNone(self.ledger.cursor('s')); self.assertEqual(self.result()['sample_count'], 0)
        self.ledger.ingest([usage()], source='s', cursor={'offset': 1})
        with self.assertRaises(ValueError): self.ledger.ingest([], source='s', cursor={'offset': 2})

    def test_concurrent_importers(self):
        def write(_):
            db = CanonicalLedger(self.path)
            try: db.ingest([usage(1, 100), usage(2, 130)])
            finally: db.close()
        with ThreadPoolExecutor(4) as pool: list(pool.map(write, range(10)))
        self.assertEqual(self.result()['known_total_tokens'], 30)
        self.assertEqual(self.result()['sample_count'], 2)
