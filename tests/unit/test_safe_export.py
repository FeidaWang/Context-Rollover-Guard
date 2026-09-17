import json
from pathlib import Path
import tempfile
import unittest
from crg.export import preview, write_approved
from crg.events import project
from crg.privacy import local_identity
from tests.unit.test_events import usage


class ExportTests(unittest.TestCase):
    def test_injected_strings_and_new_aliases(self):
        row=usage(source='/private/user/token@example.invalid');row['prompt']='secret';row['data']['tool_output']='secret'
        one=preview([project(row)]);two=preview([project(row)])
        self.assertNotEqual(one['bundle']['records'][0]['alias'],two['bundle']['records'][0]['alias'])
        encoded=json.dumps(one)
        for text in ('secret','token@example','/private','workspace_id','thread_id'):
            self.assertNotIn(text,encoded)
        row['data']['total_tokens']='high-entropy-private'
        with self.assertRaises(ValueError):preview([project(row)])

    def test_approval_and_recovery_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();pending=root/'pending';pending.write_bytes(b'exact pending prompt')
            bundle=preview([usage()]);path=root/'private/export.json'
            with self.assertRaises(ValueError):write_approved(bundle,path,approved_sha256='wrong')
            write_approved(bundle,path,approved_sha256=bundle['sha256'])
            self.assertEqual(pending.read_bytes(),b'exact pending prompt')
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(local_identity('account',root/'private/key'),local_identity('account',root/'private/key'))

    def test_interchange_units_dedup_and_remap(self):
        from crg.export import interchange
        import csv,io
        one=interchange([usage(),usage()]);two=interchange([usage()])
        rows=[json.loads(line) for line in one.splitlines()]
        self.assertEqual(len(rows),1);self.assertNotEqual(one,two)
        self.assertEqual(rows[0]['time_unit'],'milliseconds')
        parsed=list(csv.DictReader(io.StringIO(interchange([usage()],format='csv'))))
        self.assertEqual(parsed[0]['total_tokens'],'100')
        self.assertNotIn('account_id',one)

    def test_identity_key_special_file_refused(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();key=root/'key';os.mkfifo(key)
            with self.assertRaises(ValueError):local_identity('account',key)
