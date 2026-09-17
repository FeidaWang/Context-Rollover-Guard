import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('offline_runner',ROOT/'scripts/verify_offline.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class OfflineRunnerTests(unittest.TestCase):
    def test_snapshot_excludes_private_state_and_path_traversal(self):
        for name in ('docs/context-rollover/evidence/log.json','.codex/auth.json','crg/.env',
                     '../crg/cli.py','/tmp/crg/cli.py','crg/__pycache__/cli.pyc','crg/auth.json'):
            self.assertFalse(runner.selected(name),name)
        for name in ('crg/cli.py','tests/unit/test_archive.py','skills/context-rollover-guard/SKILL.md'):
            self.assertTrue(runner.selected(name),name)

    def test_environment_does_not_inherit_secrets_or_startup_paths(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'OPENAI_API_KEY':'synthetic', 'PYTHONPATH':'untrusted', 'HTTPS_PROXY':'untrusted'}):
            env=runner.environment(Path(temp), ROOT)
            self.assertNotIn('OPENAI_API_KEY',env)
            self.assertNotIn('HTTPS_PROXY',env)
            self.assertNotIn('untrusted',env.values())
            self.assertEqual(list((Path(temp)/'home').iterdir()),[])
            self.assertEqual(list((Path(temp)/'codex').iterdir()),[])

    def test_os_probe_bypasses_python_guard_and_propagates_failure(self):
        import subprocess
        with patch.object(runner.subprocess,'run',side_effect=subprocess.CalledProcessError(1, ['probe'])) as run:
            with self.assertRaises(subprocess.CalledProcessError): runner.assert_os_network({},ROOT)
            self.assertIn('-I',run.call_args.args[0])
            self.assertTrue(run.call_args.kwargs['check'])
