import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from tests.support.fixtures import FIXTURE_ROOT, fixture_path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = FIXTURE_ROOT


class PublicFixtures(unittest.TestCase):
    def test_complete_manifest_hashes_provenance_and_consumers(self):
        manifest = json.loads(fixture_path('manifest.json').read_text())
        entries = manifest['fixtures']
        actual = {p.relative_to(FIXTURES).as_posix() for p in FIXTURES.rglob('*')
                  if p.is_file() and p.name not in {'README.md', 'manifest.json'}}
        self.assertEqual(len(entries), len({entry['path'] for entry in entries}))
        self.assertEqual({entry['path'] for entry in entries}, actual)
        for entry in entries:
            with self.subTest(fixture=entry['path']):
                data = fixture_path(entry['path']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
                self.assertEqual(len(data), entry['size_bytes'])
                self.assertEqual(entry['evidence_grade'], 'synthetic')
                self.assertEqual(entry['origin'], 'hand-authored public fixture; see README.md')
                self.assertIs(entry['captured_user_content'], False)
                self.assertIs(entry['live_runtime_authority'], False)
                self.assertTrue(entry['consumers'])
                for consumer in entry['consumers']:
                    path = (ROOT / consumer).resolve()
                    self.assertTrue(path.is_relative_to(ROOT))
                    self.assertTrue(path.is_file(), consumer)

    def test_resolver_rejects_missing_or_outside_inputs(self):
        with self.assertRaises(FileNotFoundError):
            fixture_path('missing-public-fixture.json')
        for name in ('../support', str(ROOT / 'tests/support')):
            with self.subTest(path=name), self.assertRaises(ValueError):
                fixture_path(name)

    def test_fixture_privacy_and_synthetic_provenance(self):
        for path in FIXTURES.rglob('*'):
            if path.suffix not in {'.json', '.jsonl'}:
                continue
            text = path.read_text()
            self.assertIsNone(re.search(r'sk-[A-Za-z0-9]{16,}|-----BEGIN .*PRIVATE KEY|Bearer [A-Za-z0-9]|/Users/|/Applications/', text), str(path))
        # Projected events have a closed field set: no raw transcript strings.
        allowed = {'method', 'params', 'threadId', 'turnId', 'tokenUsage', 'last', 'total',
                   'modelContextWindow', 'totalTokens', 'inputTokens', 'outputTokens',
                   'cachedInputTokens', 'reasoningOutputTokens', 'turn', 'id', 'status', 'items', 'error'}
        strings = {'thread', 'one', 'two', 'three', 'four', 'compact', 'completed',
                   'thread/tokenUsage/updated', 'turn/completed', 'thread/compacted'}
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(set(value)-allowed)
                for item in value.values(): check(item)
            elif isinstance(value, list):
                self.assertEqual(value, [])
            elif isinstance(value, str):
                self.assertIn(value, strings)
        for line in (FIXTURES/'compaction-events.jsonl').read_text().splitlines():
            check(json.loads(line))
        manifest = json.loads((FIXTURES/'protocol/capabilities.json').read_text())
        self.assertEqual(manifest['codex_version'], 'synthetic-offline-v1')
        self.assertEqual(manifest['schema_sha256']['ClientRequest.json'], hashlib.sha256((FIXTURES/'protocol/schema/ClientRequest.json').read_bytes()).hexdigest())

    def test_offline_guard_rejects_network_and_live_runtime(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT/'tests/support/offline_guard'))
        for code in ["import socket; socket.create_connection(('127.0.0.1', 9))", "import subprocess; subprocess.run(['codex', '--version'])"]:
            result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Offline verification forbids', result.stderr)

    def test_offline_guard_allows_subprocess_without_allowing_direct_spawn(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT/'tests/support/offline_guard'))
        code = "import subprocess,sys; subprocess.run([sys.executable, '-c', 'print(123)'], close_fds=False, check=True)"
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '123')
        if hasattr(os, 'posix_spawn'):
            code = "import os,sys; os.posix_spawn(sys.executable, [sys.executable, '-c', 'print(123)'], os.environ)"
            result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Offline verification forbids unguarded process launch', result.stderr)
            self.assertEqual(result.stdout, '')
