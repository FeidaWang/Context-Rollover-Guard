"""Synthetic policy and migration contracts; never a live-capability certificate."""
from dataclasses import replace
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crg.cli import main
from crg.config import Config, Continuity, Emergency, General, load_config
from crg.config_migration import migrate
from crg.domain import SessionState
from crg.hooks import HookDispatcher
from crg.repo_hook import dispatch_repo
from crg.state_store import StateStore


class ContinuityConfig(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = Config(context_rollover=General(enabled=True, mode='MODE_B'),
                             emergency=Emergency(block_auto_compact=True, force_rollover_on_next_prompt=True))
        self.store = StateStore(self.root/'state', self.root, 's')
        self.store.update(lambda s: s, initial=replace(SessionState.create(self.root, 's', 't'), mode='MODE_B'))
        self.base = dict(cwd=str(self.root), session_id='s', thread_id='t', turn_id='one')

    def test_cooperation_ignores_legacy_blocking_even_with_adapter_flags(self):
        handler = HookDispatcher(self.store, self.config, allow_warning=True,
                                 allow_prompt_block=True, allow_precompact_block=True, configured_limit=1)
        self.assertEqual(handler.dispatch(self.base | dict(hook_event_name='PreCompact', trigger='auto')), {})
        self.assertEqual(self.store.read().state, 'NORMAL')
        self.assertTrue(Path(self.store.read().telemetry['guard']['emergency_snapshot']).is_file())
        self.store.update(lambda s: replace(s, state='ARMED', last_active_context_tokens=100, model_context_window=100))
        self.assertEqual(handler.dispatch(self.base | dict(hook_event_name='Stop', last_assistant_message=' exact\r\n🙂')), {})
        self.assertEqual(Path(self.store.read().pending_answer_path).read_bytes(), ' exact\r\n🙂'.encode())
        self.assertEqual(handler.dispatch(self.base | dict(hook_event_name='UserPromptSubmit', prompt=' untouched')), {})
        self.assertEqual(list(self.store.directory.glob('prompt-*.json')), [])

    def test_policy_cannot_upgrade_mode_or_capability(self):
        config = replace(self.config, continuity=Continuity('guarded_owned_rollover'))
        handler = HookDispatcher(self.store, config)
        self.store.update(lambda s: replace(s, state='ARMED'))
        self.assertEqual(handler.dispatch(self.base | dict(hook_event_name='UserPromptSubmit', prompt='x')), {})
        self.store.update(lambda s: replace(s, mode='MODE_A'))
        handler.allow_prompt_block = True
        self.assertEqual(handler.dispatch(self.base | dict(hook_event_name='UserPromptSubmit', prompt='x')), {})
        self.assertEqual(self.store.read().mode, 'MODE_A')

    def test_observe_is_read_only_and_manual_recovery_does_not_intercept(self):
        before = self.store.read().to_dict()
        for policy in ('observe', 'manual_recovery'):
            handler = HookDispatcher(self.store, replace(self.config, continuity=Continuity(policy)), allow_prompt_block=True)
            self.assertEqual(handler.dispatch(self.base | dict(hook_event_name='UserPromptSubmit', prompt='x')), {})
        handler.config = replace(self.config, continuity=Continuity('observe'))
        self.assertEqual(handler.dispatch(self.base | dict(hook_event_name='Stop')), {})
        self.assertEqual(self.store.read().to_dict(), before)

    def test_cli_flags_are_not_capability_verification(self):
        (self.root/'crg.toml').write_text('[context_rollover]\nenabled=true\n[continuity]\npolicy="guarded_owned_rollover"\n[emergency]\nforce_rollover_on_next_prompt=true\n')
        self.store.update(lambda s: replace(s, state='ARMED'))
        event = self.base | dict(hook_event_name='UserPromptSubmit', prompt='x')
        with contextlib.redirect_stdout(io.StringIO()) as output, patch('sys.stdin', io.StringIO(json.dumps(event))):
            code = main(['hook', '--workspace', str(self.root), '--session', 's', '--thread', 't',
                         '--state-root', str(self.root/'state'), '--allow-prompt-block'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), {})
        self.assertEqual(list(self.store.directory.glob('prompt-*.json')), [])

    def test_repo_mode_and_legacy_options_do_not_verify_interception(self):
        (self.root/'crg.toml').write_text('[context_rollover]\nenabled=true\nmode="MODE_B"\nstate_root="repo-state"\n'
                                       '[continuity]\npolicy="guarded_owned_rollover"\n'
                                       '[emergency]\nblock_auto_compact=true\nforce_rollover_on_next_prompt=true\n')
        result = dispatch_repo(self.base | dict(thread_id='s', hook_event_name='PreCompact', trigger='auto'), self.root)
        self.assertNotIn('continue', result)
        result = dispatch_repo(self.base | dict(thread_id='s', hook_event_name='UserPromptSubmit', prompt='x'), self.root)
        self.assertNotIn('decision', result)


class ConfigMigration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root/'crg.toml'
        self.original = b'# Keep this comment\r\n[context_rollover]\r\nenabled=true\r\nmode="MODE_B"\r\n[predictor]\r\nwarn_probability=0.6\r\n[emergency]\r\nblock_auto_compact=true\r\n'
        self.source.write_bytes(self.original)
        self.pending = self.root/'pending.json'
        self.pending.write_bytes(b'{"state":"RECOVERY_REQUIRED","exact":" original "}')

    def test_preview_and_explicit_candidate_preserve_original_and_recovery(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = migrate(self.root)
        self.assertTrue(result['dry_run'])
        self.assertTrue(any('deprecated and ignored' in text for text in result['diagnostics']))
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['config', 'migrate', '--workspace', str(self.root), '--apply',
                                   '--output', 'candidate.toml', '--expected-sha256', result['source_sha256']]), 0)
        self.assertFalse(json.loads(output.getvalue())['dry_run'])
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(self.pending.read_bytes(), before['pending.json'])
        candidate = self.root/'candidate.toml'
        self.assertTrue(candidate.read_bytes().startswith(self.original))
        config = load_config(self.root, user_file=candidate, repo_file=candidate)
        self.assertEqual(config.continuity.policy, 'native_cooperative')
        self.assertTrue(config.emergency.block_auto_compact)  # preserved but not authority
        self.assertTrue(config.rollover.preserve_permissions)

    def test_apply_refuses_stale_overwrite_and_missing_preview_binding(self):
        digest = migrate(self.root)['source_sha256']
        for kwargs in ({}, {'output':'crg.toml','expected_sha256':digest},
                       {'output':'candidate.toml','expected_sha256':'bad'},
                       {'output':'../outside.toml','expected_sha256':digest}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                migrate(self.root, apply=True, **kwargs)
        candidate = self.root/'candidate.toml'
        candidate.write_text('existing')
        with self.assertRaises(ValueError):
            migrate(self.root, apply=True, output=candidate, expected_sha256=digest)
        candidate.unlink()  # synthetic test-owned candidate only
        candidate.symlink_to(self.source)
        with self.assertRaises(ValueError):
            migrate(self.root, apply=True, output=candidate, expected_sha256=digest)
        self.source.write_bytes(self.original+b'\n# concurrent edit')
        with self.assertRaises(ValueError):
            migrate(self.root, apply=True, output='new.toml', expected_sha256=digest)

    def test_policy_validation_and_cli_diagnostics(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['config', '--workspace', str(self.root)]), 0)
        self.assertTrue(any('deprecated' in line for line in json.loads(output.getvalue())['warnings']))
        with self.assertRaises(ValueError):
            load_config(self.root, user_file=self.source, overrides={'continuity': {'policy':'invented'}})
        with self.assertRaises(ValueError):
            load_config(self.root, user_file=self.source, overrides={'rollover': {'preserve_permissions':False}})
