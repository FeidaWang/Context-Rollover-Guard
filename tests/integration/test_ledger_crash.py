"""Real process death around SQLite observation/cursor commit boundaries."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from crg.ledger import CanonicalLedger
from tests.unit.test_events import usage


class LedgerCrashTests(unittest.TestCase):
    def test_process_death_and_replay(self):
        for stage in ('after_observations', 'before_commit', 'after_commit'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temp:
                path = Path(temp).resolve() / 'private/ledger.sqlite'
                script = '''
import os,sys
from crg.ledger import CanonicalLedger
from tests.unit.test_events import usage
ledger=CanonicalLedger(sys.argv[1])
def fault(stage):
    if stage==sys.argv[2]: os._exit(79)
ledger.ingest([usage(1,100),usage(2,130)],source='s',cursor={'offset':2},fault=fault)
'''
                done = subprocess.run([sys.executable, '-c', script, str(path), stage], timeout=20)
                self.assertEqual(done.returncode, 79)
                db = CanonicalLedger(path)
                try:
                    committed = stage == 'after_commit'
                    self.assertEqual(db.cursor('s'), {'offset': 2} if committed else None)
                    db.ingest([usage(1,100), usage(2,130)], source='s',
                              expected_cursor=db.cursor('s'), cursor={'offset':2})
                    self.assertEqual(db.usage('local','2026-09-17T00:00:00Z','2026-09-18T00:00:00Z')['known_total_tokens'],30)
                finally: db.close()
