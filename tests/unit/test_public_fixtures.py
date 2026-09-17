import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT/'tests/fixtures'


class PublicFixtures(unittest.TestCase):
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
