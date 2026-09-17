import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('crg_release_builder', ROOT/'scripts/build_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        for directory in ('crg', 'scripts', 'skills/context-rollover-guard'):
            shutil.copytree(ROOT/directory, self.root/directory, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        for name in ('pyproject.toml', 'LICENSE', 'README.md', '.codex-plugin/plugin.json'):
            (self.root/name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, self.root/name)
        mock = patch.object(release.subprocess, 'check_output', side_effect=self.git)
        mock.start(); self.addCleanup(mock.stop)

    def git(self, args, **kwargs):
        if args[1] == 'rev-parse': return 'a'*40+'\n'
        return b' M crg/config.py\x00'

    def build(self):
        return release.build_release(self.root, epoch=1700000000)

    def test_recursive_package_resources_and_reproducibility(self):
        nested = self.root/'crg/nested'; nested.mkdir()
        (nested/'__init__.py').write_text('')
        (nested/'data.json').write_text('{"resource": true}')
        cache = nested/'__pycache__'; cache.mkdir(); (cache/'ignored.pyc').write_bytes(b'cache')
        first = self.build()
        before = release.files(self.root/'dist')
        self.assertEqual(first['result'], 'PASS')
        self.assertTrue(first['source_dirty'])
        self.build()
        self.assertEqual(before, release.files(self.root/'dist'))
        members = release.unpack((self.root/'dist/crg.pyz').read_bytes())
        self.assertIn('crg/nested/data.json', members)
        self.assertNotIn('crg/nested/__pycache__/ignored.pyc', members)
        self.assertEqual((self.root/'dist/crg.pyz').read_bytes(), (self.root/'dist/context-rollover-guard/scripts/crg.pyz').read_bytes())
        self.assertTrue((self.root/'dist/crg.pyz').read_bytes().startswith(b'#!/usr/bin/env python3\n'))

    def test_version_disagreement_rejected_before_output_changes(self):
        self.build()
        before = release.files(self.root/'dist')
        (self.root/'crg/__init__.py').write_text('__version__ = "wrong"\n')
        with self.assertRaisesRegex(ValueError, 'version'): self.build()
        self.assertEqual(before, release.files(self.root/'dist'))

    def test_artifact_corruption_and_manifest_drift(self):
        self.build()
        pyz = self.root/'dist/crg.pyz'
        original = pyz.read_bytes(); pyz.write_bytes(original+b'corrupt')
        with self.assertRaisesRegex(ValueError, 'SHA-256'): release.verify(self.root)
        pyz.write_bytes(original)
        path = self.root/'dist/context-rollover-guard.manifest.json'
        doc = json.loads(path.read_text()); doc['build']['package_version'] = 'wrong'
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'manifests disagree'): release.verify(self.root)

    def test_updated_hashes_cannot_hide_packaged_version_mismatch(self):
        self.build()
        dist = self.root/'dist'
        entries = release.unpack((dist/'crg.pyz').read_bytes())
        entries['crg/__init__.py'] = b'__version__ = "wrong"\n'
        damaged = release.archive(entries, executable=True)
        (dist/'crg.pyz').write_bytes(damaged)
        (dist/'context-rollover-guard/scripts/crg.pyz').write_bytes(damaged)
        manifest = json.loads((dist/'MANIFEST.json').read_text())
        for name in ('crg.pyz', 'context-rollover-guard/scripts/crg.pyz'):
            manifest['artifacts'][name] = release.digest(damaged)
        for name in ('MANIFEST.json','context-rollover-guard.manifest.json'):
            (dist/name).write_bytes(release.canonical(manifest))
        with self.assertRaisesRegex(ValueError, 'Packaged source/version'): release.verify(self.root)

    def test_source_drift_and_zip_inventory_mismatch(self):
        self.build()
        source = self.root/'crg/config.py'
        source.write_bytes(source.read_bytes()+b'\n# drift\n')
        with self.assertRaisesRegex(ValueError, 'Source snapshot'): release.verify(self.root)
        self.build()
        dist = self.root/'dist'
        entries = release.unpack((dist/'context-rollover-guard.zip').read_bytes())
        entries['context-rollover-guard/unexpected.txt'] = b'extra'
        data = release.archive(entries)
        (dist/'context-rollover-guard.zip').write_bytes(data)
        manifest = json.loads((dist/'MANIFEST.json').read_bytes())
        manifest['artifacts']['context-rollover-guard.zip'] = release.digest(data)
        for name in ('MANIFEST.json','context-rollover-guard.manifest.json'):
            (dist/name).write_bytes(release.canonical(manifest))
        with self.assertRaisesRegex(ValueError, 'Skill ZIP'): release.verify(self.root)

    def test_failed_staging_does_not_publish_partial_release(self):
        self.build()
        before = release.files(self.root/'dist')
        with patch.object(release, 'verify', side_effect=ValueError('staging failure')):
            with self.assertRaisesRegex(ValueError, 'staging failure'): self.build()
        self.assertEqual(before, release.files(self.root/'dist'))

    def test_symlink_source_is_rejected(self):
        (self.root/'crg/linked.py').symlink_to(self.root/'crg/config.py')
        with self.assertRaisesRegex(ValueError, 'Symlink'): self.build()

    def test_interrupted_publication_is_detected(self):
        self.build()
        replace_file = release.os.replace
        count = 0
        def interrupt(source, target):
            nonlocal count
            count += 1
            if count == 2: raise OSError('interrupted publication')
            return replace_file(source, target)
        with patch.object(release.os, 'replace', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'interrupted publication'):
                release.build_release(self.root, epoch=1700000001)
        with self.assertRaisesRegex(ValueError, 'SHA-256'): release.verify(self.root)

    def test_verify_command_returns_failure(self):
        import contextlib
        import io
        self.build()
        (self.root/'dist/crg.pyz').write_bytes(b'corrupt')
        with patch.object(release, 'ROOT', self.root), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(release.main(['--verify']), 1)
        self.assertEqual(json.loads(output.getvalue())['result'], 'FAIL')

    def test_different_directories_same_inputs_and_epoch(self):
        self.build()
        with tempfile.TemporaryDirectory() as temp:
            other = Path(temp)/'checkout'
            shutil.copytree(self.root, other)
            release.build_release(other, epoch=1700000000)
            self.assertEqual(release.files(self.root/'dist'), release.files(other/'dist'))

    def test_epoch_changes_provenance_and_environment_is_respected(self):
        with patch.dict(release.os.environ, {'SOURCE_DATE_EPOCH': '1700000042'}):
            release.build_release(self.root)
        info = json.loads((self.root/'dist/MANIFEST.json').read_bytes())['build']
        self.assertEqual(info['epoch'], 1700000042)

    def test_license_wheel_record_and_sdist_core(self):
        import base64
        import csv
        import io
        import tarfile
        self.build()
        wheel = release.unpack(next((self.root/'dist').glob('*.whl')).read_bytes())
        record = next(k for k in wheel if k.endswith('/RECORD'))
        for name, checksum, size in csv.reader(io.StringIO(wheel[record].decode())):
            if name == record:
                self.assertEqual((checksum,size), ('',''))
            else:
                self.assertEqual(int(size), len(wheel[name]))
                self.assertEqual(checksum, 'sha256='+base64.urlsafe_b64encode(release.hashlib.sha256(wheel[name]).digest()).decode().rstrip('='))
        self.assertEqual(wheel['crg/cli.py'], (self.root/'crg/cli.py').read_bytes())
        self.assertEqual(wheel[next(k for k in wheel if k.endswith('/LICENSE'))], (self.root/'LICENSE').read_bytes())
        with tarfile.open(next((self.root/'dist').glob('*.tar.gz'))) as archive:
            name = next(n for n in archive.getnames() if n.endswith('/crg/cli.py'))
            self.assertEqual(archive.extractfile(name).read(), wheel['crg/cli.py'])
            self.assertTrue(all(m.uid == m.gid == 0 and m.mode == 0o644 for m in archive.getmembers()))

    def test_private_input_rejected_before_publication(self):
        self.build()
        before = release.files(self.root/'dist')
        (self.root/'crg/auth.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Private state'): self.build()
        self.assertEqual(before, release.files(self.root/'dist'))

    def test_absolute_home_and_key_signatures_rejected(self):
        for data in (b'/Users/example/private', b'/home/example/private', b'sk-'+b'a'*24):
            with self.assertRaisesRegex(ValueError, 'Sensitive signature'):
                release.scan({'data.txt':data})

    def test_disposable_snapshot_provenance_needs_no_git_commit(self):
        with patch.object(release.subprocess, 'check_output', side_effect=AssertionError('No Git access in snapshot build')):
            result = release.build_release(self.root, epoch=1700000000,
                                           provenance={'commit':'b'*40, 'dirty':True})
        self.assertEqual(result['source_commit'], 'b'*40)
        self.assertTrue(result['source_dirty'])
        with self.assertRaisesRegex(ValueError, 'provenance'):
            release.build_release(self.root, provenance={'commit':'invalid','dirty':True})
