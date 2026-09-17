from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from crg.config import Config,General,Emergency
from crg.domain import SessionState,State,Mode
from crg.state_store import StateStore
from crg.hooks import HookDispatcher
from crg.archive import ArchiveManager


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.cwd=self.root/'workspace';self.cwd.mkdir()
        self.store=StateStore(self.root/'state',self.cwd,'session')
        self.initial=replace(SessionState.create(self.cwd,'session','thread'),mode=Mode.B.value)
        self.store.update(lambda s:s,initial=self.initial)
        self.config=Config(context_rollover=General(enabled=True,mode='MODE_B'),
                           emergency=Emergency(block_auto_compact=True,force_rollover_on_next_prompt=True))
        self.handler=HookDispatcher(self.store,self.config,allow_prompt_block=True,allow_precompact_block=True,
                                    archive_root=self.root/'archives')
        self.base={'session_id':'session','thread_id':'thread','cwd':str(self.cwd)}
        self.handler.dispatch(self.base|{'hook_event_name':'Stop','turn_id':'previous','last_assistant_message':'上一轮\r\n🙂'})
        self.store.update(lambda s:replace(s,state='ARMED'))
        self.prompt=self.base|{'hook_event_name':'UserPromptSubmit','turn_id':'new','prompt':' 原始\r\n🙂\n'}

    def test_prompt_captured_before_archive_failure_and_never_forwarded(self):
        def failure(*args):
            files=list(self.store.directory.glob('prompt-*.json'))
            self.assertEqual(len(files),1)
            self.assertEqual(json.loads(files[0].read_text())['text'],self.prompt['prompt'])
            raise OSError('disk fault')
        with patch.object(ArchiveManager,'prepare',side_effect=failure):result=self.handler.dispatch(self.prompt)
        self.assertEqual(result['decision'],'block')
        self.assertEqual(self.store.read().state,'RECOVERY_REQUIRED')

    def test_capture_archive_and_duplicate_submission(self):
        result=self.handler.dispatch(self.prompt)
        self.assertEqual(result['decision'],'block')
        state=self.store.read();self.assertEqual(state.state,'ROLLOVER_PREPARING')
        directory=Path(state.telemetry['guard']['archive_dir'])
        self.assertEqual(json.loads((directory/'prompt.json').read_text())['text'],self.prompt['prompt'])
        self.assertEqual((directory/'answer.md').read_bytes(),'上一轮\r\n🙂'.encode())
        revision=state.revision
        self.handler.dispatch(self.prompt)
        self.assertEqual(self.store.read().revision,revision)
        self.assertEqual(len(list(self.store.directory.glob('prompt-*.json'))),1)

    def test_second_prompt_is_queued_without_overwriting_first(self):
        self.handler.dispatch(self.prompt);first=self.store.read().rollover_id
        self.handler.dispatch(self.prompt|{'turn_id':'newer','prompt':'第二条'})
        state=self.store.read()
        self.assertEqual(state.rollover_id,first)
        self.assertEqual(len(state.telemetry['guard']['submissions']),2)
        texts={json.loads(p.read_text())['text'] for p in self.store.directory.glob('prompt-*.json')}
        self.assertEqual(texts,{self.prompt['prompt'],'第二条'})

    def test_recovery_captures_without_replaying(self):
        self.store.update(lambda s:s.transition(State.RECOVERY))
        result=self.handler.dispatch(self.prompt)
        self.assertEqual(result['decision'],'block')
        self.assertEqual(self.store.read().state,'RECOVERY_REQUIRED')
        self.assertEqual(len(list(self.store.directory.glob('prompt-*.json'))),1)

    def test_normal_and_observe_do_not_intercept(self):
        self.store.update(lambda s:replace(s,mode=Mode.A.value))
        self.assertEqual(self.handler.dispatch(self.prompt),{})
        self.assertEqual(len(list(self.store.directory.glob('prompt-*.json'))),0)

    def test_auto_snapshot_before_block_and_idempotency(self):
        event=self.base|{'hook_event_name':'PreCompact','turn_id':'compact','trigger':'auto'}
        output=self.handler.dispatch(event)
        self.assertIs(output['continue'],False)
        state=self.store.read();self.assertEqual(state.state,'EMERGENCY')
        snapshot=Path(state.telemetry['guard']['emergency_snapshot'])
        self.assertTrue(snapshot.exists())
        self.handler.dispatch(event)
        self.assertEqual(len(list(self.store.directory.glob('emergency-*.json'))),1)
        self.assertEqual(self.handler.dispatch(self.prompt)['decision'],'block')

    def test_manual_compaction_unaffected(self):
        rev=self.store.read().revision
        self.assertEqual(self.handler.dispatch(self.base|{'hook_event_name':'PreCompact','turn_id':'compact','trigger':'manual'}),{})
        self.assertEqual(self.store.read().revision,rev)

    def test_block_requires_both_config_and_verified_capability(self):
        handler=HookDispatcher(self.store,self.config,allow_precompact_block=False)
        output=handler.dispatch(self.base|{'hook_event_name':'PreCompact','turn_id':'compact','trigger':'auto'})
        self.assertNotIn('continue',output)
        self.assertEqual(self.store.read().state,'EMERGENCY')

    def test_emergency_force_false_does_not_intercept_prompt(self):
        self.handler.dispatch(self.base|{'hook_event_name':'PreCompact','turn_id':'compact','trigger':'auto'})
        self.handler.config=replace(self.config,emergency=Emergency(force_rollover_on_next_prompt=False))
        self.assertEqual(self.handler.dispatch(self.prompt),{})
        self.assertEqual(list(self.store.directory.glob('prompt-*.json')),[])

    def test_prediction_miss_preserved_on_duplicate_auto_hook(self):
        other=StateStore(self.root/'other-state',self.cwd,'session')
        other.update(lambda s:s,initial=self.initial)
        handler=HookDispatcher(other,self.config,allow_precompact_block=True)
        event=self.base|{'hook_event_name':'PreCompact','turn_id':'compact','trigger':'auto'}
        handler.dispatch(event)
        self.assertTrue(other.read().telemetry['guard']['prediction_miss'])
        revision=other.read().revision
        handler.dispatch(event)
        self.assertTrue(other.read().telemetry['guard']['prediction_miss'])
        self.assertEqual(other.read().revision,revision)
