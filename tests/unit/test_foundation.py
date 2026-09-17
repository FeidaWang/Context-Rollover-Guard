from dataclasses import replace
from pathlib import Path
import hashlib
import json
import multiprocessing as mp
import os
import tempfile
import unittest
from unittest.mock import patch
from crg.config import load_config, ConfigurationError
from crg.domain import SessionState, State
from crg.state_store import (StateStore, StoreError, CorruptState, FutureSchema,
                             RecoveryRequired, Conflict, canonical, decode, encode)
from crg.capability_probe import select_mode, inspect_schema, probe


def writer(root, cwd, count):
    store = StateStore(Path(root), Path(cwd), "session")
    for _ in range(count):
        store.update(lambda s: replace(s, last_active_context_tokens=s.last_active_context_tokens + 1))


def crash_writer(root, cwd, stage):
    def crash(point):
        if stage == point:
            os._exit(77)
    store = StateStore(Path(root), Path(cwd), "session", fault=crash)
    store.update(lambda s: replace(s, last_active_context_tokens=999))


class Foundation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.cwd = self.base / "workspace"; self.cwd.mkdir()
        self.root = self.base / "state"
        self.initial = SessionState.create(self.cwd, "session", "thread")

    def store(self, **kwargs):
        return StateStore(self.root, self.cwd, "session", **kwargs)

    def initialize(self):
        return self.store().update(lambda s: replace(s, last_active_context_tokens=10), initial=self.initial)

    def test_transition_graph_and_acceptance_gate(self):
        s = self.initial
        self.assertIs(s.transition(State.NORMAL), s)
        with self.assertRaises(ValueError): s.transition(State.ARCHIVING)
        s = s.transition(State.ARMED)
        with self.assertRaises(ValueError): s.transition(State.PREPARING)
        s = s.transition(State.PREPARING, evidence={"prompt_persisted": True})
        s = s.transition(State.STARTING, evidence=dict(prompt_persisted=True, answer_archived=True, handoff_written=True))
        s = s.transition(State.FORWARDING, evidence={"new_thread_started": True})
        with self.assertRaises(ValueError): s.transition(State.ARCHIVING)
        s = s.transition(State.ARCHIVING, evidence={"turn_accepted": True})
        s = s.transition(State.NORMAL, evidence={"transaction_committed": True})
        self.assertEqual(s.state, "NORMAL")
        with self.assertRaises(ValueError): s.transition(State.RECOVERY).transition(State.NORMAL)

    def test_every_state_can_fail_closed(self):
        for state in State:
            self.assertEqual(replace(self.initial, state=state.value).transition(State.RECOVERY).state, State.RECOVERY.value)

    def test_round_trip_idempotency_cas_and_timestamp(self):
        first = self.initialize(); store = self.store()
        self.assertEqual(first, store.read())
        self.assertEqual(store.update(lambda s: s), first)
        second = store.update(lambda s: replace(s, model="custom"), expected_revision=first.revision)
        self.assertGreater(second.revision, first.revision)
        self.assertGreaterEqual(second.updated_at, first.updated_at)
        with self.assertRaises(Conflict): store.update(lambda s: s, expected_revision=first.revision)

    def test_atomic_io_order(self):
        stages=[]
        store=self.store(fault=stages.append)
        store.update(lambda s:s, initial=self.initial)
        self.assertEqual(stages, [f'{label}:{stage}' for label in ('backup','primary')
                                 for stage in ('partial','fsync','rename','dirsync')])
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(store.directory.stat().st_mode & 0o777, 0o700)

    def test_concurrent_processes_no_lost_updates(self):
        self.initialize()
        ctx = mp.get_context("spawn")
        processes = [ctx.Process(target=writer, args=(str(self.root),str(self.cwd),30)) for _ in range(4)]
        for p in processes: p.start()
        for p in processes:
            p.join(20)
            self.assertFalse(p.is_alive())
            self.assertEqual(p.exitcode,0)
        self.assertEqual(self.store().read().last_active_context_tokens,130)

    def test_process_crash_at_every_write_boundary(self):
        self.initialize()
        ctx = mp.get_context("spawn")
        for label in ("backup", "primary"):
            for step in ("partial", "fsync", "rename", "dirsync"):
                with self.subTest(label=label, step=step):
                    self.store().update(lambda s: replace(s,last_active_context_tokens=10))
                    p=ctx.Process(target=crash_writer,args=(str(self.root),str(self.cwd),f'{label}:{step}'))
                    p.start(); p.join(10)
                    self.assertEqual(p.exitcode,77)
                    state=self.store().read()
                    self.assertIn(state.last_active_context_tokens,(10,999))
                    self.assertEqual(decode(self.store().path.read_bytes()),state)

    def test_corrupt_primary_backup_recovery_and_preserve_evidence(self):
        self.initialize()
        self.store().update(lambda s: replace(s, model="next"))
        store=self.store(); store.path.write_bytes(b'{broken')
        self.assertEqual(store.read().state,State.RECOVERY.value)
        with self.assertRaises(RecoveryRequired): store.update(lambda s:s)
        restored=store.repair()
        self.assertEqual(restored,store.read())
        self.assertEqual(list(store.directory.glob('state.corrupt.*.json'))[0].read_bytes(),b'{broken')
        with self.assertRaises(RecoveryRequired): store.update(lambda s:s)

    def test_both_corrupt_fail_closed(self):
        self.initialize(); s=self.store()
        s.path.write_bytes(b'{}');s.backup.write_bytes(b'null')
        with self.assertRaises(CorruptState): s.read()
        with self.assertRaises(CorruptState): s.update(lambda s:s,initial=self.initial)

    def test_checksum_tampering(self):
        self.initialize(); store=self.store()
        d=json.loads(store.path.read_bytes()); d['payload']['state']='ARMED'
        store.path.write_text(json.dumps(d))
        self.assertEqual(store.read().state, State.RECOVERY.value)

    def test_future_schema_never_falls_back(self):
        self.initialize(); s=self.store(); payload=self.initial.to_dict();payload['schema_version']=99
        s.path.write_bytes(canonical({'format_version':1,'payload':payload,
                                     'sha256':hashlib.sha256(canonical(payload)).hexdigest()}))
        with self.assertRaises(FutureSchema):s.read()
        with self.assertRaises(FutureSchema):s.repair()

    def test_v0_migration_is_non_actionable(self):
        s=self.store(); d=self.initial.to_dict();d['schema_version']=0;d.pop('revision')
        s.path.write_bytes(canonical(d));s.path.chmod(0o600)
        migrated=s.read()
        self.assertEqual(migrated.schema_version,1)
        self.assertEqual(migrated.state,State.RECOVERY.value)
        with self.assertRaises(RecoveryRequired):s.update(lambda s:s)
        s.repair()
        self.assertIn("payload", json.loads(s.path.read_bytes()))
        self.assertEqual(s.read().state,State.RECOVERY.value)

    def test_identity_graph_and_invalid_values(self):
        self.initialize()
        for change in ({'session_id':'different'},{'state':State.ARCHIVING.value},
                       {'last_active_context_tokens':True},{'risk_score':float('nan')},{'revision':-1}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.store().update(lambda s:replace(s,**change))

    def test_path_escape_and_symlinks(self):
        escaped=StateStore(self.root,self.cwd,'../../escape')
        self.assertTrue(escaped.directory.is_relative_to(self.root))
        other=self.base/'other';other.mkdir(mode=0o700)
        link=self.base/'link';link.symlink_to(other)
        with self.assertRaises(StoreError): StateStore(link,self.cwd,'s')
        self.initialize();s=self.store(); s.path.unlink();s.path.symlink_to(self.base/'victim')
        with self.assertRaises(OSError):s.read()
        self.assertFalse((self.base/'victim').exists())

    def test_store_enforces_transition_evidence(self):
        self.initialize(); store=self.store()
        store.update(lambda s:replace(s,state=State.ARMED.value))
        with self.assertRaises(ValueError):store.update(lambda s:replace(s,state=State.PREPARING.value))
        store.update(lambda s:replace(s,state=State.PREPARING.value),evidence={"prompt_persisted":True})
        self.assertEqual(store.read().state,State.PREPARING.value)

    def test_lock_timeout(self):
        store=self.store(timeout=0)
        with store._lock():
            with self.assertRaises(TimeoutError):self.store(timeout=0).read()

    def test_initial_partial_write_is_not_normal(self):
        def fail(stage):
            if stage=='primary:partial':raise OSError('fault')
        with self.assertRaises(OSError): self.store(fault=fail).update(lambda s:s,initial=self.initial)
        self.assertEqual(self.store().read().state,State.RECOVERY.value)

    def test_config_precedence_and_safe_defaults(self):
        user=self.base/'user.toml';repo=self.cwd/'crg.toml'
        user.write_text('[predictor]\nmin_growth_tokens=100\nwindow_size=3\n')
        repo.write_text('[predictor]\nmin_growth_tokens=200\n')
        c=load_config(self.cwd,user_file=user,overrides={'predictor':{'min_growth_tokens':300}})
        self.assertEqual(c.predictor.min_growth_tokens,300)
        self.assertEqual(c.predictor.window_size,3)
        self.assertFalse(c.context_rollover.enabled)
        self.assertFalse(c.emergency.block_auto_compact)
        self.assertFalse(c.paths(self.cwd)[1].exists() and str(c.paths(self.cwd)[1]).startswith(str(self.base)))

    def test_config_rejects_bad_values_and_disabled_invariants(self):
        for override in ({'x':{}},{'predictor':{'window_size':False}},
                         {'predictor':{'safety_buffer_percent':float('nan')}},
                         {'predictor':{'window_size':0}}, {'predictor':{'min_growth_tokens':-1}},
                         {'context_rollover':{'enabled':'true'}}, {'context_rollover':{'mode':'fast'}},
                         {'rollover':{'preserve_cwd':False}}, {'predictor':{'typo':3}}):
            with self.subTest(override=override), self.assertRaises(ConfigurationError):
                load_config(self.cwd,user_file=self.base/'missing',overrides=override)

    def test_config_invalid_toml(self):
        p=self.cwd/'crg.toml';p.write_text('[invalid')
        with self.assertRaises(ConfigurationError):load_config(self.cwd,user_file=self.base/'missing')

    def test_capability_fails_closed(self):
        self.assertEqual(select_mode({}), 'MODE_A')
        self.assertEqual(select_mode({'owns_active_transport':'true'}), 'MODE_A')
        guarded=dict(stop_payload_verified=True,prompt_interception_verified=True,
                     hook_execution_trusted=True,lossless_answer_verified=True)
        self.assertEqual(select_mode(guarded),'MODE_B')
        self.assertEqual(select_mode(guarded | dict(owns_active_transport=True,fresh_thread_verified=True,
            same_cwd_verified=True,exact_once_verified=True,archive_order_verified=True)),'MODE_C')
        result=probe(self.cwd,self.base/'probe',binary='crg-no-such-binary-xyz')
        self.assertEqual(result['selected_mode'],'MODE_A')
        self.assertTrue(result['errors'])

    def test_installed_schema_contract(self):
        path=Path(__file__).resolve().parents[2]/'docs/context-rollover/evidence/schema'
        result=inspect_schema(path)
        self.assertTrue(all(result['methods'].values()))
        self.assertTrue(all(result['hooks_supported'].values()))
        self.assertTrue(result['token_usage_supported'])
        self.assertTrue(result['client_user_message_id_supported'])


if __name__=='__main__':unittest.main()
