import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from crg.config import load_config, resolve_config
from crg.cli import main

ROOT = Path(__file__).resolve().parents[2]


class SafeDefaults(unittest.TestCase):
    def test_repository_defaults_are_inert(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = load_config(ROOT, user_file=Path(tmp)/'missing')
            self.assertFalse(c.context_rollover.enabled)
            self.assertEqual(c.context_rollover.mode, 'auto')
            with patch.dict(os.environ, CODEX_HOME=tmp), patch('subprocess.Popen', side_effect=AssertionError('runtime mutation')):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(['hook', '--workspace', str(ROOT), '--session', 's', '--thread', 't', '--state-root', tmp+'/state', '--allow-prompt-block', '--allow-precompact-block']), 0)
                self.assertEqual(json.loads(output.getvalue()), {})
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_import_has_no_filesystem_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, HOME=tmp, CODEX_HOME=tmp+'/codex', PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
            code = '''import sys

def audit(event, args):
    if event in {'os.mkdir', 'os.remove', 'os.rename', 'subprocess.Popen', 'socket.connect'}:
        raise AssertionError(event)
    if event == 'open' and isinstance(args[2], int) and args[2] & 3:
        raise AssertionError('write')
sys.addaudithook(audit)
import importlib, pkgutil, crg
for module in pkgutil.iter_modules(crg.__path__):
    if module.name != '__main__': importlib.import_module('crg.' + module.name)
from pathlib import Path
from crg.config import load_config
load_config(Path.cwd())
'''
            run = subprocess.run([sys.executable, '-B', '-c', code], cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_config_without_codex_binary_uses_runtime_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, CODEX_HOME=tmp):
                self.assertEqual(load_config(Path(tmp)).context_rollover.codex_binary, '')
                with patch('crg.cli.probe', return_value={}) as probe, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['doctor', '--probe', '--workspace', tmp]), 0)
                self.assertEqual(probe.call_args.args[2], 'codex')

    def test_emergency_blocking_is_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = load_config(ROOT, user_file=Path(tmp)/'missing')
            self.assertFalse(c.emergency.block_auto_compact)
            self.assertFalse(c.emergency.force_rollover_on_next_prompt)

    def test_provenance_and_cli_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'user.toml').write_text('[context_rollover]\ncodex_binary="local-runtime"\n[predictor]\nwindow_size=3\n')
            (root/'crg.toml').write_text('[predictor]\nwindow_size=4\n')
            c, sources = resolve_config(root, root/'user.toml', overrides={'predictor': {'min_growth_tokens': 5}})
            self.assertEqual(c.predictor.window_size, 4)
            self.assertEqual(sources['predictor']['window_size'], 'repo')
            self.assertEqual(sources['predictor']['min_growth_tokens'], 'cli')
            self.assertEqual(sources['context_rollover']['codex_binary'], 'user')
            self.assertEqual(sources['context_rollover']['enabled'], 'default')
            with patch.dict(os.environ, CODEX_HOME=tmp), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['config', '--workspace', tmp, '--codex', 'chosen']), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result['context_rollover']['codex_binary'], 'chosen')
            self.assertEqual(result['sources']['context_rollover']['codex_binary'], 'cli')
