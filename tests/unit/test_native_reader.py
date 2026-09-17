import json
import os
from pathlib import Path
import tempfile
import unittest
from crg.ledger import CanonicalLedger
from crg.native_reader import BoundReader
from tests.unit.test_events import usage


class NativeReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(); self.path = self.root / 'log.jsonl'
        self.db = CanonicalLedger(self.root / 'private/db'); self.addCleanup(self.db.close)
        self.path.write_bytes(b'')

    def reader(self, **kw):
        return BoundReader(self.db, self.path, authorized_root=self.root,
                           session_id='s', runtime_version='current', **kw)

    def test_append_partial_copy_and_replay(self):
        first = json.dumps(usage(1,100)).encode()+b'\n'
        second = json.dumps(usage(2,130)).encode()+b'\n'
        self.path.write_bytes(first+second[:30])
        reader = self.reader(); self.assertEqual(reader.read()['records'], 1)
        with self.path.open('ab') as out: out.write(second[30:])
        self.assertEqual(reader.read()['records'], 1)
        self.assertEqual(reader.read()['records'], 0)
        copy = self.root / 'copy'; copy.write_bytes(self.path.read_bytes())
        BoundReader(self.db, copy, authorized_root=self.root, session_id='s', runtime_version='current').read()
        self.assertEqual(self.db.db.execute('SELECT count(*) FROM fact').fetchone()[0], 2)

    def test_rotation_truncation_and_runtime(self):
        self.path.write_text(json.dumps(usage())+'\n'); reader = self.reader(); reader.read()
        self.path.write_bytes(b'')
        with self.assertRaises(ValueError): reader.read()
        self.path.unlink(); self.path.write_text(json.dumps(usage())+'\n')
        # Same event on a explicitly re-bound runtime is still one billing fact.
        BoundReader(self.db, self.path, authorized_root=self.root,session_id='s',runtime_version='new').read()
        self.assertEqual(self.db.db.execute('SELECT count(*) FROM fact').fetchone()[0],1)

    def test_large_idle_history_has_bounded_reads(self):
        with self.path.open('wb') as out:
            out.seek(100*1024*1024-1); out.write(b'\n')
        reader = self.reader(); reader.read(bootstrap_at_end=True)
        self.assertLessEqual(reader.read()['bytes_read'],256)

    def test_special_files_and_unbound_paths(self):
        self.path.unlink(); os.mkfifo(self.path)
        with self.assertRaises(ValueError): self.reader().read()
        self.path.unlink(); self.path.symlink_to(self.root/'missing')
        with self.assertRaises(OSError): self.reader().read()
        with self.assertRaises(ValueError):
            BoundReader(self.db, self.root.parent/'outside',authorized_root=self.root,session_id='s',runtime_version='r')
        with self.assertRaises(ValueError):
            BoundReader(self.db,self.root,authorized_root=self.root,session_id='s',runtime_version='r')
