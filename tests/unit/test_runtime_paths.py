from dataclasses import replace
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from crg.config import load_config, resolve_config
from crg.runtime_paths import RuntimePaths
from crg.diagnostics import diagnose, initialize
from crg.cli import main

ROOT = Path(__file__).resolve().parents[2]


class RuntimePathTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.workspace = self.root/'project'; self.workspace.mkdir()
        env = patch.dict(os.environ, CODEX_HOME=str(self.root/'home'))
        env.start(); self.addCleanup(env.stop)

    def config(self, **values):
        return resolve_config(self.workspace, overrides={'context_rollover': values})

    def test_defaults_are_lazy_and_independent_of_checkout(self):
        config, sources = self.config()
        paths = RuntimePaths.resolve(self.workspace, config)
        self.assertEqual(paths.state_root, self.root/'home/context-rollover')
        self.assertEqual(paths.schema_cache, paths.state_root/'runtime/schema')
        self.assertEqual(paths.capability_receipt, paths.state_root/'runtime/capabilities.json')
        self.assertEqual(paths.hook_receipts, paths.state_root/'hooks')
        self.assertIsNone(paths.evidence_exports)
        self.assertEqual(config.paths(self.workspace), (paths.archive_root, paths.state_root))
        self.assertEqual(list(self.workspace.iterdir()), [])
        self.assertFalse((self.root/'home').exists())

    def test_all_explicit_paths_and_legacy_override(self):
        config, _ = self.config(state_root='state', archive_root='archive', schema_cache='cache/schema',
                               capability_receipt='receipts/cap.json', hook_receipts='hooks', evidence_exports='exports')
        paths = RuntimePaths.resolve(self.workspace, config)
        self.assertEqual(paths.schema_cache, self.workspace/'cache/schema')
        self.assertEqual(paths.capability_receipt, self.workspace/'receipts/cap.json')
        self.assertEqual(paths.hook_review, self.workspace/'hooks/mode-b-runtime-review.json')
        self.assertEqual(paths.evidence_exports, self.workspace/'exports')
        legacy = RuntimePaths.resolve(self.workspace, config, evidence='explicit-old-location')
        self.assertEqual(legacy.schema_cache, self.workspace/'explicit-old-location/schema')
        self.assertEqual(legacy.capability_receipt, self.workspace/'explicit-old-location/capabilities.json')

    def test_init_is_disabled_and_never_overwrites(self):
        initialize(self.workspace)
        before = (self.workspace/'crg.toml').read_bytes()
        config = load_config(self.workspace)
        self.assertFalse(config.context_rollover.enabled)
        self.assertFalse(config.emergency.block_auto_compact)
        self.assertEqual(list(self.workspace.iterdir()), [self.workspace/'crg.toml'])
        with self.assertRaises(ValueError): initialize(self.workspace)
        self.assertEqual((self.workspace/'crg.toml').read_bytes(), before)

    def test_init_refuses_symlink(self):
        target = self.root/'target'; target.write_text('keep')
        (self.workspace/'crg.toml').symlink_to(target)
        with self.assertRaises(ValueError): initialize(self.workspace)
        self.assertEqual(target.read_text(), 'keep')

    def test_doctor_missing_runtime_and_evidence_is_read_only(self):
        config, sources = self.config()
        with patch('crg.diagnostics.shutil.which', return_value=None), patch('subprocess.Popen', side_effect=AssertionError('launch')):
            result = diagnose(self.workspace, config, sources)
        for key in ('configured','runtime_available','schema_verified','hooks_discovered','guard_enabled','guard_active_for_session'):
            self.assertIs(result[key], False, key)
        for key in ('hooks_trusted', 'telemetry_available'):
            self.assertIsNone(result[key])
        self.assertFalse((self.root/'home').exists())
        self.assertNotIn('production_enabled', result)

    def test_configured_enabled_is_not_session_active(self):
        config, sources = self.config(enabled=True, mode='MODE_B')
        result = diagnose(self.workspace, config, sources)
        self.assertTrue(result['configured'])
        self.assertTrue(result['guard_enabled'])
        self.assertIsNone(result['guard_active_for_session'])
        self.assertTrue(result['warnings'])

    def test_schema_integrity_and_runtime_binding_not_live_trust(self):
        config, sources = self.config(codex_binary=sys.executable)
        paths = RuntimePaths.resolve(self.workspace, config)
        shutil.copytree(ROOT/'tests/fixtures/protocol/schema', paths.schema_cache)
        receipt = json.loads((ROOT/'tests/fixtures/protocol/capabilities.json').read_text())
        receipt.update(binary=sys.executable, schema_generation_ok=True, generated_at='2000-01-01T00:00:00Z')
        paths.capability_receipt.write_text(json.dumps(receipt))
        result = diagnose(self.workspace, config, sources)
        self.assertTrue(result['runtime_available'])
        self.assertTrue(result['schema_verified'])
        self.assertIsNone(result['hooks_trusted'])
        self.assertIsNone(result['telemetry_available'])
        (paths.schema_cache/'ClientRequest.json').write_text('{}')
        self.assertFalse(diagnose(self.workspace, config, sources)['schema_verified'])
        import hashlib
        receipt['schema_sha256']['ClientRequest.json'] = hashlib.sha256(b'{}').hexdigest()
        paths.capability_receipt.write_text(json.dumps(receipt))
        self.assertFalse(diagnose(self.workspace, config, sources)['schema_verified'])
        receipt['binary'] = '/missing/runtime'
        paths.capability_receipt.write_text(json.dumps(receipt))
        self.assertFalse(diagnose(self.workspace, config, sources)['schema_verified'])

    def test_malformed_receipt_and_hooks_stay_unknown(self):
        config, sources = self.config()
        paths = RuntimePaths.resolve(self.workspace, config)
        paths.capability_receipt.parent.mkdir(parents=True)
        paths.capability_receipt.write_text('[]')
        (self.workspace/'.codex').mkdir()
        (self.workspace/'.codex/hooks.json').write_text('{"hooks":{"Stop":[{"unverified":true}]}}')
        result = diagnose(self.workspace, config, sources)
        self.assertTrue(result['hooks_discovered'])
        self.assertIsNone(result['hooks_trusted'])
        self.assertTrue(result['errors'])

    def test_doctor_json_and_human(self):
        for fmt in ('json', 'human'):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['doctor','--workspace',str(self.workspace),'--format',fmt]), 0)
            if fmt == 'json': self.assertIn('schema_verified', json.loads(output.getvalue()))
            else: self.assertIn('hooks_trusted: UNKNOWN', output.getvalue())

    def test_owned_client_uses_configured_schema_and_manifest(self):
        from crg.owned_client import run_chat
        config, _ = self.config(enabled=True, mode='MODE_B', schema_cache='schemas', capability_receipt='receipts/runtime.json')
        with patch('crg.config.load_config', return_value=config), patch('crg.appserver.ProtocolSchema', side_effect=ValueError('stop before RPC')) as schema:
            with self.assertRaisesRegex(ValueError, 'stop before RPC'):
                run_chat(SimpleNamespace(workspace=self.workspace, schema=None))
        self.assertEqual(schema.call_args.args[0], self.workspace/'schemas')
        self.assertEqual(schema.call_args.kwargs['manifest_path'], self.workspace/'receipts/runtime.json')

    def test_probe_respects_separate_paths_and_optional_export(self):
        from crg.capability_probe import probe
        config, _ = self.config(schema_cache='cache/schema', capability_receipt='receipts/capabilities.json', evidence_exports='export')
        paths = RuntimePaths.resolve(self.workspace, config)
        def fake_run(args, **kwargs):
            if 'generate-json-schema' in args:
                destination = Path(args[args.index('--out')+1])
                shutil.copytree(ROOT/'tests/fixtures/protocol/schema', destination, dirs_exist_ok=True)
            return SimpleNamespace(returncode=0, stdout='codex-cli fixture', stderr='')
        with patch('crg.capability_probe.inventory', return_value={}), patch('crg.capability_probe.shutil.which', return_value=sys.executable), patch('crg.capability_probe.subprocess.run', side_effect=fake_run), patch('crg.capability_probe.isolated_rpc', return_value={'initialize_ok': True}):
            probe(self.workspace, self.root/'unused', paths=paths)
        self.assertTrue((paths.schema_cache/'ClientRequest.json').exists())
        self.assertEqual(paths.capability_receipt.stat().st_mode & 0o777, 0o600)
        self.assertTrue((paths.evidence_exports/'CAPABILITY_REPORT.md').exists())
        self.assertFalse((self.root/'unused').exists())
        from crg.appserver import ProtocolSchema
        ProtocolSchema(paths.schema_cache, manifest_path=paths.capability_receipt)

    def test_probe_missing_binary_creates_only_private_receipt(self):
        from crg.capability_probe import probe
        config, _ = self.config()
        paths = RuntimePaths.resolve(self.workspace, config)
        with patch('crg.capability_probe.inventory', return_value={}), patch('crg.capability_probe.shutil.which', return_value=None):
            result = probe(self.workspace, paths.capability_receipt.parent, paths=paths)
        self.assertTrue(result['errors'])
        self.assertTrue(paths.capability_receipt.exists())
        self.assertFalse(paths.schema_cache.exists())
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_hook_install_cli_uses_resolved_receipt_root(self):
        config, _ = self.config(hook_receipts='receipts/hooks')
        with patch('crg.cli.load_config', return_value=config), patch('crg.installer.install_hooks', return_value={}) as install, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['install-hooks', '--workspace', str(self.workspace), '--hooks-file', str(self.workspace/'.codex/hooks.json'), '--dispatcher-argv', '["synthetic-hook"]', '--apply']), 0)
        self.assertEqual(install.call_args.args[1], self.workspace/'receipts/hooks')
