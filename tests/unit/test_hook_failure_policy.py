"""Offline fault injection only; no installed hooks or runtime contract claims."""
from dataclasses import replace
from pathlib import Path
import errno
import importlib
import io
import json
import os
import stat
import tempfile
import unittest
from unittest.mock import patch

from crg.durable import read_private, open_private_lock
from crg.hook_failure import failure_output
from crg.state_store import StateStore, StoreError
from tests.unit import test_guard
from tests.support.live_policy import LivePolicyError, verify_effective_hooks


class HookFailurePolicyTests(unittest.TestCase):
    def test_stop_failures_are_nonblocking_and_content_free(self):
        for exc in (OSError(errno.ENOSPC,'secret'),PermissionError('secret'),TimeoutError('secret'),ValueError('secret')):
            result,code=failure_output({'hook_event_name':'Stop'},exc)
            self.assertEqual(code,0)
            self.assertNotIn('decision',result)
            self.assertNotIn('secret',json.dumps(result))
            self.assertIn('unavailable',result['systemMessage'])

    def test_unverified_submit_never_claims_to_block(self):
        result,code=failure_output({'hook_event_name':'UserPromptSubmit'},TimeoutError())
        self.assertEqual(code,1)
        self.assertNotIn('decision',result)
        self.assertIn('CRG_BLOCKING_UNSUPPORTED',result['systemMessage'])

    def test_known_risky_capture_failure_blocks_without_false_durability_claim(self):
        fixture=test_guard.GuardTests('test_capture_archive_and_duplicate_submission')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        before=fixture.store.path.read_bytes()
        for exc in (OSError(errno.ENOSPC,'full'),PermissionError(),TimeoutError(),ValueError('corrupt')):
            with patch('crg.hooks.immutable_write',side_effect=exc):
                result=fixture.handler.dispatch(fixture.prompt)
            self.assertEqual(result['decision'],'block')
            self.assertIn('could not confirm',result['reason'])
            self.assertEqual(fixture.store.path.read_bytes(),before)
        self.assertFalse(list(fixture.store.directory.glob('prompt-*.json')))

    def test_unreadable_guard_state_blocks_in_verified_adapter(self):
        fixture=test_guard.GuardTests('test_capture_archive_and_duplicate_submission')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        with patch.object(fixture.store,'read',side_effect=StoreError('corrupt')):
            self.assertEqual(fixture.handler.dispatch(fixture.prompt)['decision'],'block')

    def test_repo_entry_stop_exit_zero_submit_error_nonzero(self):
        import importlib.util
        path=Path(__file__).resolve().parents[2]/'scripts/repo_hook.py'
        spec=importlib.util.spec_from_file_location('repo_entry',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for event,expected in [('Stop',0),('UserPromptSubmit',1)]:
            incoming=io.TextIOWrapper(io.BytesIO(json.dumps({'hook_event_name':event}).encode()))
            outgoing=io.StringIO()
            with patch('sys.argv',['repo_hook','--workspace','.']),patch('sys.stdin',incoming),patch('sys.stdout',outgoing),patch.object(module,'dispatch_repo',side_effect=PermissionError()):
                self.assertEqual(module.main(),expected)
            self.assertIsInstance(json.loads(outgoing.getvalue()),dict)
            self.assertEqual(len(outgoing.getvalue().splitlines()),1)

    def test_cli_stop_configuration_failure_is_nonblocking(self):
        from crg.cli import main
        event=json.dumps({'hook_event_name':'Stop'})
        with patch('sys.stdin',io.StringIO(event)),patch('sys.stdout',io.StringIO()) as output,patch('crg.cli.load_config',side_effect=PermissionError()):
            code=main(['hook','--workspace','.', '--state-root','state', '--session','s','--thread','t'])
        self.assertEqual(code,0)
        self.assertIn('CRG_PERMISSION_DENIED',json.loads(output.getvalue())['systemMessage'])


class SafeFileTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.file=self.root/'data';self.file.write_bytes(b'exact\r\n');self.file.chmod(0o600)

    def test_exact_regular_read_and_size_bound(self):
        self.assertEqual(read_private(self.file),b'exact\r\n')
        with self.assertRaises(ValueError):read_private(self.file,max_bytes=2)

    def test_fifo_rejected_before_open(self):
        fifo=self.root/'fifo';os.mkfifo(fifo)
        with self.assertRaises(ValueError):read_private(fifo)

    def test_device_rejected_before_open(self):
        with self.assertRaises(ValueError):read_private(Path('/dev/null'))

    def test_socket_mode_rejected_before_open(self):
        # Portable socket inode simulation; no socket.bind in offline verification.
        real=os.stat
        def info(path,*args,**kw):
            value=real(path,*args,**kw)
            if path=='data':
                fields=list(value);fields[0]=stat.S_IFSOCK|0o600
                return os.stat_result(fields)
            return value
        with patch('crg.durable.os.stat',side_effect=info):
            with self.assertRaises(ValueError):read_private(self.file)

    def test_symlink_leaf_and_parent_refused(self):
        link=self.root/'link';link.symlink_to(self.file)
        with self.assertRaises(OSError):read_private(link)
        directory=self.root/'other';directory.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):read_private(directory/'data')

    def test_foreign_ownership_and_public_permissions_refused(self):
        self.file.chmod(0o644)
        with self.assertRaises(ValueError):read_private(self.file)
        self.file.chmod(0o600)
        with patch('crg.durable.os.getuid',return_value=os.getuid()+1):
            with self.assertRaises(ValueError):read_private(self.file)

    def test_parent_substitution_does_not_redirect_read(self):
        directory=self.root/'directory';directory.mkdir();file=directory/'data'
        file.write_bytes(b'original');file.chmod(0o600)
        other=self.root/'other';other.mkdir();(other/'data').write_bytes(b'foreign')
        original=os.open;renamed=self.root/'renamed';swapped=False
        def opening(path,flags,*args,**kwargs):
            nonlocal swapped
            fd=original(path,flags,*args,**kwargs)
            if path=='directory' and not swapped:
                swapped=True;directory.rename(renamed);directory.symlink_to(other,target_is_directory=True)
            return fd
        with patch('crg.durable.os.open',side_effect=opening):
            self.assertEqual(read_private(file),b'original')

    def test_concurrent_lock_creation_reinspects_new_inode(self):
        lock=self.root/'new-lock';original=os.open;created=False
        def opening(path,flags,*args,**kwargs):
            nonlocal created
            if path=='new-lock' and flags&os.O_EXCL and not created:
                created=True
                other=original(path,flags,*args,**kwargs);os.close(other)
                raise FileExistsError()
            return original(path,flags,*args,**kwargs)
        with patch('crg.durable.os.open',side_effect=opening):
            fd=open_private_lock(lock)
        os.close(fd);self.assertTrue(created)

    def test_special_lock_and_public_lock_refused(self):
        lock=self.root/'lock';os.mkfifo(lock)
        with self.assertRaises(ValueError):open_private_lock(lock)
        lock.unlink();lock.write_bytes(b'');lock.chmod(0o644)
        with self.assertRaises(ValueError):open_private_lock(lock)

    def test_state_fifo_refused_without_hang(self):
        store=StateStore(self.root/'state',self.root,'session')
        os.mkfifo(store.path)
        with self.assertRaises(StoreError):store.read()


class LiveIsolationTests(unittest.TestCase):
    def test_every_model_entrypoint_rejects_before_side_effects(self):
        root=Path(__file__).resolve().parents[1]
        for path in root.glob('live_*.py'):
            if path.stem=='live_schema':continue
            with self.subTest(entry=path.stem):
                module=importlib.import_module('tests.'+path.stem)
                with patch('subprocess.Popen',side_effect=AssertionError('process launch')):
                    with self.assertRaisesRegex(LivePolicyError,'CRG_LIVE_DISABLED'):
                        module.main()

    def test_direct_server_and_command_only_cannot_bypass_gate(self):
        from tests.support.live_server import LiveServer
        for command_only in (False,True):
            with self.assertRaises(LivePolicyError):
                LiveServer(Path('/not-created'),command_only=command_only)

    def test_unknown_hooks_abort_exact_inventory_check(self):
        expected=[{'key':'fixture','enabled':True,'trustStatus':'trusted'}]
        verify_effective_hooks(expected,expected)
        for actual in (None,expected+[{'key':'global'}],[],[{'key':'fixture','enabled':True,'trustStatus':'unknown'}]):
            with self.assertRaises(LivePolicyError):verify_effective_hooks(actual,expected)

    def test_matching_untrusted_metadata_is_still_refused(self):
        entries=[{'key':'fixture','enabled':True,'trustStatus':'unknown'}]
        with self.assertRaises(LivePolicyError):verify_effective_hooks(entries,entries)
