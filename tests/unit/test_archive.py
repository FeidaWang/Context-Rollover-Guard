from dataclasses import replace
from pathlib import Path
import json
import multiprocessing as mp
import os
import tempfile
import unittest
from crg.archive import ArchiveManager,rollover_id
from crg.config import Config,General
from crg.domain import SessionState,State,Mode
from crg.durable import read_private
from crg.hooks import HookDispatcher,HookError,pending_answer
from crg.state_store import StateStore
from crg.telemetry import Observer
from tests.unit.test_observe import token,complete


def concurrent_archive(root,cwd):
    state=replace(SessionState.create(Path(cwd),'session','thread'),last_turn_id='turn')
    ArchiveManager(Path(root)).prepare(state,'same prompt',b'same answer')


class Archives(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.cwd=self.root/'workspace';self.cwd.mkdir()
        self.state=replace(SessionState.create(self.cwd,'session','thread'),last_turn_id='turn')
        self.archive=ArchiveManager(self.root/'archives')

    def test_exact_unicode_empty_and_long(self):
        for index,answer in enumerate(['中文\r\n🙂 e\u0301\x00尾\n','','长'*1000000]):
            prompt='  原始\r\n𠜎 prompt '+str(index)+'\n'
            folder=self.archive.prepare(self.state,prompt,answer.encode())
            self.assertEqual(read_private(folder/'answer.md'),answer.encode())
            self.assertEqual(json.loads(read_private(folder/'prompt.json'))['text'],prompt)
            self.assertTrue(self.archive.verify(folder)['verified'])
            for path in folder.iterdir():self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_resume_after_every_archive_step(self):
        for stage in ['prompt_persisted','answer_archived','handoff_written','archive_ready']:
            def fail(point):
                if point==stage:raise OSError('simulated crash')
            manager=ArchiveManager(self.root/('archive-'+stage),fault=fail)
            with self.assertRaises(OSError):manager.prepare(self.state,'prompt','回答'.encode())
            folder=ArchiveManager(manager.root).prepare(self.state,'prompt','回答'.encode())
            self.assertTrue(manager.verify(folder)['verified'])

    def test_retry_does_not_rewrite_snapshot(self):
        folder=self.archive.prepare(self.state,'prompt',b'answer')
        before={p.name:p.read_bytes() for p in folder.iterdir()}
        again=self.archive.prepare(self.state,'prompt',b'answer')
        self.assertEqual(folder,again)
        self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir()})
        with self.assertRaises(ValueError):self.archive.prepare(self.state,'prompt',b'different answer')

    def test_corruption_and_missing_manifest_fail(self):
        folder=self.archive.prepare(self.state,'prompt',b'answer')
        (folder/'answer.md').write_bytes(b'tampered')
        with self.assertRaises(ValueError):self.archive.verify(folder)

    def test_path_injection_remains_data(self):
        state=replace(self.state,last_turn_id='../../escape')
        folder=self.archive.prepare(state,'../bad\n$(touch injected)',b'answer')
        self.assertEqual(folder.parent,self.archive.root)
        self.assertFalse((self.cwd/'injected').exists())
        self.assertIn('untrusted recovery index',json.loads((folder/'handoff.json').read_text())['trust'])
        outside=self.root/'outside';outside.mkdir()
        link=self.archive.root/'crg_bad';link.symlink_to(outside)
        with self.assertRaises(ValueError):self.archive.verify(link)

    def test_workspace_handoff_no_git_is_honest(self):
        folder=self.archive.prepare(self.state,'prompt',b'answer')
        h=json.loads((folder/'handoff.json').read_text())
        self.assertEqual(h['workspace']['cwd'],str(self.cwd))
        self.assertIsNone(h['workspace']['git_head'])
        self.assertEqual(h['previous_answer'],str(folder/'answer.md'))

    def test_concurrent_archive_same_request(self):
        ctx=mp.get_context('spawn');processes=[ctx.Process(target=concurrent_archive,args=(str(self.archive.root),str(self.cwd))) for _ in range(3)]
        for p in processes:p.start()
        for p in processes:p.join(15)
        for p in processes:self.assertEqual(p.exitcode,0)
        self.assertEqual(len(list(self.archive.root.glob('crg_*'))),1)
        self.assertTrue(self.archive.verify(next(self.archive.root.glob('crg_*')))['verified'])


class StopHandler(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.cwd=self.root/'workspace';self.cwd.mkdir()
        self.store=StateStore(self.root/'state',self.cwd,'session')
        self.initial=replace(SessionState.create(self.cwd,'session','thread'),mode=Mode.B.value)
        self.store.update(lambda s:s,initial=self.initial)
        self.config=Config(context_rollover=General(enabled=True,mode='MODE_B'))
        self.observer=Observer(self.store,self.config)
        self.handler=HookDispatcher(self.store,self.config,allow_warning=True,configured_limit=20000,scope='total')
        self.event={'hook_event_name':'Stop','session_id':'session','thread_id':'thread','cwd':str(self.cwd),
                    'turn_id':'1','last_assistant_message':' 原文\r\n🙂\n','stop_hook_active':False}

    def test_stop_before_turn_completed_caches_and_warns_once(self):
        self.observer.ingest(token('1',15000))
        output=self.handler.dispatch(self.event)
        self.assertIn('systemMessage',output)
        self.assertNotIn('continue',output);self.assertNotIn('decision',output)
        self.assertEqual(self.store.read().state,'ARMED')
        self.assertEqual(pending_answer(self.store.read()),self.event['last_assistant_message'].encode())
        self.assertEqual(self.handler.dispatch(self.event),{})
        self.observer.ingest(complete('1'))
        self.assertEqual(self.store.read().state,'ARMED')

    def test_disabled_no_writes(self):
        revision=self.store.read().revision
        handler=HookDispatcher(self.store,Config())
        self.assertEqual(handler.dispatch(self.event),{})
        self.assertEqual(self.store.read().revision,revision)

    def test_observe_never_warns(self):
        self.store.update(lambda s:replace(s,mode=Mode.A.value))
        self.observer.ingest(token('1',250000))
        self.assertEqual(self.handler.dispatch(self.event),{})
        self.assertEqual(self.store.read().state,'NORMAL')

    def test_no_telemetry_no_prediction_no_warning(self):
        self.assertEqual(self.handler.dispatch(self.event),{})
        self.assertEqual(self.store.read().telemetry['guard']['stop_prediction']['decision'],'UNKNOWN')

    def test_null_answer_is_not_archived_as_empty(self):
        self.handler.dispatch(self.event|{'last_assistant_message':''})
        self.assertEqual(pending_answer(self.store.read()),b'')
        with self.assertRaises(HookError):self.handler.dispatch(self.event|{'turn_id':'2','last_assistant_message':None})
        self.assertEqual(self.store.read().state,'RECOVERY_REQUIRED')
        with self.assertRaises(HookError):pending_answer(self.store.read())

    def test_identity_and_pending_integrity(self):
        with self.assertRaises(HookError):self.handler.dispatch(self.event|{'session_id':'wrong'})
        self.handler.dispatch(self.event)
        Path(self.store.read().pending_answer_path).write_bytes(b'tamper')
        with self.assertRaises(HookError):pending_answer(self.store.read())

    def test_same_turn_revised_answer_retains_both_originals(self):
        self.handler.dispatch(self.event);old=Path(self.store.read().pending_answer_path)
        self.handler.dispatch(self.event|{'last_assistant_message':'revised'})
        self.assertEqual(read_private(old),self.event['last_assistant_message'].encode())
        self.assertEqual(pending_answer(self.store.read()),b'revised')
