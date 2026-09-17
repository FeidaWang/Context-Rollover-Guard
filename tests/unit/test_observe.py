from tests.support.fixtures import fixture_path
from dataclasses import replace
from pathlib import Path
import copy
import json
import tempfile
import unittest
from crg.config import Config, Predictor
from crg.domain import SessionState
from crg.state_store import StateStore
from crg.predictor import predict,resolve_limit
from crg.telemetry import Observer,TelemetryError,parse_usage
from crg.logging import append_event,read_events


def token(turn,active,total=900000,window=272000):
    def block(n):return dict(totalTokens=n,inputTokens=n,outputTokens=0,cachedInputTokens=0,reasoningOutputTokens=0)
    return {'method':'thread/tokenUsage/updated','params':dict(threadId='thread',turnId=turn,
        tokenUsage=dict(last=block(active),total=block(total),modelContextWindow=window))}


def complete(turn):
    return {'method':'turn/completed','params':dict(threadId='thread',turn=dict(id=turn,status='completed',items=[],error=None))}


class PredictionTests(unittest.TestCase):
    def test_empty_history(self):
        result=predict(10000,100000,[],resolve_limit(100000,scope='total'))
        self.assertEqual(result['decision'],'SAFE')
        self.assertEqual(result['predicted_growth'],8000)
        self.assertFalse(result['calibrated_probability'])

    def test_large_latest_growth(self):
        result=predict(50000,100000,[1000,1000,40000],resolve_limit(100000,scope='total'))
        self.assertEqual(result['predicted_growth'],40000)
        self.assertEqual(result['decision'],'ARM')

    def test_steady_growth(self):
        result=predict(10000,100000,[10000]*8,resolve_limit(100000,scope='total'))
        self.assertEqual(result['predicted_growth'],12500)
        self.assertEqual(result['decision'],'SAFE')

    def test_headroom_and_over_limit(self):
        for active in (89000,110000):
            result=predict(active,100000,[],resolve_limit(100000,scope='total'))
            self.assertEqual(result['decision'],'ARM')
            self.assertLessEqual(result['risk_score'],1)

    def test_custom_limit_and_nonstandard_window(self):
        self.assertEqual(resolve_limit(123456,60000,scope='total').tokens,60000)
        self.assertEqual(resolve_limit(123456,999999,scope='total').tokens,111110)
        self.assertEqual(resolve_limit(100000,scope='unknown').tokens,80000)

    def test_body_scope(self):
        limit=resolve_limit(100000,70000,scope='body_after_prefix')
        self.assertEqual(limit.source,'conservative_estimate')
        self.assertFalse(limit.precise)
        self.assertEqual(resolve_limit(100000,70000,scope='body_after_prefix',prefix_tokens=5000).tokens,75000)

    def test_unknown_window_never_guessed(self):
        self.assertIsNone(resolve_limit(None,200000).tokens)
        self.assertEqual(predict(200000,None,[],resolve_limit(None))['decision'],'UNKNOWN')

    def test_invalid_telemetry_and_counts(self):
        for active in (-1,True,float('nan')):
            with self.assertRaises(ValueError):predict(active,100000,[],resolve_limit(100000))
        with self.assertRaises(ValueError):predict(10,100000,[-5],resolve_limit(100000))
        with self.assertRaises(ValueError):resolve_limit(100000,scope='invented')


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.cwd=self.root/'workspace';self.cwd.mkdir()
        self.store=StateStore(self.root/'state',self.cwd,'session')
        self.initial=SessionState.create(self.cwd,'session','thread')
        self.observer=Observer(self.store,Config(),initial=self.initial,scope='total')

    def turn(self,turn,active):
        self.observer.ingest(token(turn,active));return self.observer.ingest(complete(turn))

    def test_active_not_cumulative(self):
        result=self.turn('1',10000)
        self.assertEqual(self.store.read().last_active_context_tokens,10000)
        self.assertEqual(result['prediction']['decision'],'SAFE')
        self.assertEqual(self.store.read().telemetry['samples'][0]['session_cumulative_tokens'],900000)

    def test_many_updates_in_one_turn_and_duplicate_events(self):
        self.observer.ingest(token('1',10000));self.observer.ingest(token('1',12000))
        self.assertEqual(self.store.read().telemetry['positive_deltas'],[])
        self.observer.ingest(complete('1'))
        self.turn('2',22000)
        self.assertEqual(self.store.read().telemetry['positive_deltas'],[10000])
        revision=self.store.read().revision
        self.observer.ingest(complete('2'));self.observer.ingest(token('2',22000))
        self.assertEqual(self.store.read().revision,revision)

    def test_observation_never_arms_or_warns(self):
        self.turn('1',210000);result=self.turn('2',240000)
        self.assertEqual(result['prediction']['decision'],'ARM')
        self.assertEqual(result['state'],'NORMAL')
        self.assertIsNone(result['production_action'])
        self.assertFalse((self.cwd/'.codex/hooks.json').exists())

    def test_compaction_resets_and_unknown_hook_trigger(self):
        self.turn('1',200000);self.turn('2',220000)
        pre={'method':'hook/started','params':dict(threadId='thread',turnId='2',run=dict(id='h1',eventName='preCompact'))}
        self.observer.ingest(pre);self.observer.ingest(pre)
        t=self.store.read().telemetry
        self.assertEqual(len(t['precompact_samples']),1)
        self.assertEqual(t['precompact_samples'][0]['trigger'],'unknown')
        compact={'method':'thread/compacted','params':dict(threadId='thread',turnId='2')}
        result=self.observer.ingest(compact)
        self.assertIsNone(result['prediction'])
        self.assertIsNone(self.store.read().last_active_context_tokens)
        self.turn('3',30000)
        self.assertEqual(self.store.read().telemetry['positive_deltas'],[])
        self.turn('4',40000)
        self.assertEqual(self.store.read().telemetry['positive_deltas'],[10000])

    def test_drop_without_notification_is_conservative_reset(self):
        self.turn('1',200000);self.turn('2',230000);self.turn('3',50000)
        state=self.store.read()
        self.assertEqual(state.telemetry['positive_deltas'],[])
        self.assertEqual(state.telemetry['last_boundary_source'],'context_drop_observed')

    def test_restart_retains_series_and_rejects_wrong_thread(self):
        self.turn('1',10000)
        observer=Observer(self.store,Config(),scope='total')
        observer.ingest(token('2',20000));observer.ingest(complete('2'))
        self.assertEqual(self.store.read().telemetry['positive_deltas'],[10000])
        event=token('3',30000);event['params']['threadId']='other'
        with self.assertRaises(TelemetryError):observer.ingest(event)
        self.assertEqual(self.store.read().last_turn_id,'2')

    def test_missing_last_never_uses_total(self):
        event=token('1',1000);del event['params']['tokenUsage']['last']
        with self.assertRaises(TelemetryError):self.observer.ingest(event)
        self.assertIsNone(self.store.read())

    def test_null_window_unknown(self):
        self.observer.ingest(token('1',10000,window=None))
        self.assertEqual(self.observer.ingest(complete('1'))['prediction']['decision'],'UNKNOWN')

    def test_missing_or_unordered_events_refused(self):
        with self.assertRaises(TelemetryError):self.observer.ingest(complete('1'))
        self.observer.ingest(token('1',10000))
        with self.assertRaises(TelemetryError):self.observer.ingest(token('2',20000))

    def test_corrupt_history_refused(self):
        self.turn('1',1000)
        self.store.update(lambda s:replace(s,telemetry=s.telemetry|{'positive_deltas':[-100]}))
        with self.assertRaises(TelemetryError):self.turn('2',2000)

    def test_projection_does_not_log_prompt_or_unknown_fields(self):
        event=token('1',10000);event['params']['secret']='secret-not-to-record'
        self.observer.ingest(event)
        self.observer.ingest({'method':'turn/start','params':{'prompt':'secret-not-to-record'}})
        log=(self.store.directory/'telemetry.jsonl').read_text()
        self.assertNotIn('secret-not-to-record',log)
        self.assertEqual(len(list(read_events(self.store.directory/'telemetry.jsonl'))),1)

    def test_log_tail_damage_does_not_corrupt_next_record(self):
        path=self.store.directory/'telemetry.jsonl';path.write_bytes(b'{broken');path.chmod(0o600)
        self.observer.ingest(token('1',10000))
        self.assertEqual(len(list(read_events(path))),1)

class SyntheticCompactionRegression(unittest.TestCase):
    def test_projected_compaction_turn_does_not_pollute_growth(self):
        # Synthetic projected events: 3 user turns, separate compact turn, then user turn.
        events=[json.loads(line) for line in (fixture_path('compaction-events.jsonl')).read_text().splitlines()]
        thread=events[0]['params']['threadId']
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();cwd=root/'workspace';cwd.mkdir()
            store=StateStore(root/'state',cwd,thread)
            observer=Observer(store,Config(),initial=SessionState.create(cwd,thread,thread))
            for event in events:observer.ingest(event)
            state=store.read();samples=state.telemetry['samples']
            self.assertEqual([x['kind'] for x in samples],['conversation']*3+['compaction','conversation'])
            self.assertEqual(state.telemetry['series'],1)
            self.assertEqual(state.telemetry['positive_deltas'],[])
            self.assertEqual(state.last_active_context_tokens,samples[-1]['active_context_tokens'])
            self.assertNotEqual(state.last_active_context_tokens,samples[-1]['session_cumulative_tokens'])
            self.assertEqual(state.state,'NORMAL')
