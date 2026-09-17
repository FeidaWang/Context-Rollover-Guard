import copy
import unittest

from crg.native_calibration import correlate


class NativeCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.turn = '11111111-1111-1111-1111-111111111111'
        self.rows = [
            self.row(1, 'codex_models_manager::manager', 'models cache: evaluating cache eligibility client_version="0.153.4"'),
            self.row(2, 'codex_core::session::turn', 'turn{model=gpt-6-astra}: post sampling token usage '
                     f'turn_id={self.turn} total_usage_tokens=245477 auto_compact_scope_tokens=245477 '
                     'auto_compact_scope_limit=Some(244800) auto_compact_limit_scope=Total token_limit_reached=true'),
            self.row(3, 'feedback_tags', f'turn{{turn.id={self.turn}}}:run_auto_compact{{reason=ContextLimit phase=MidTurn}}: marker')]
        self.boundaries = [{'session': 's', 'turn': self.turn, 'model': 'gpt-6-astra', 'ts': 110}]

    def row(self, id, target, body):
        return {'id': id, 'ts': 100 + id, 'target': target, 'feedback_log_body': body,
                'process_uuid': 'process', 'thread_id': 's'}

    def test_exact_limit_with_three_way_evidence(self):
        result = correlate(self.rows, self.boundaries)
        sample = result['samples'][0]
        self.assertEqual(sample['observed_compact_limit'], 244800)
        self.assertEqual(sample['active_context_tokens'], 245477)
        self.assertEqual(result['groups'][0]['status'], 'INSUFFICIENT_REAL_BOUNDARIES')
        self.assertIsNone(result['groups'][0]['recall'])

    def test_missing_automatic_or_completed_boundary_is_not_a_sample(self):
        self.assertEqual(correlate(self.rows[:-1], self.boundaries)['samples'], [])
        self.assertEqual(correlate(self.rows, [])['samples'], [])

    def test_foreign_model_thread_turn_and_time_are_excluded(self):
        for key, value in [('model', 'other'), ('session', 'other'), ('turn', 'other'), ('ts', 10000)]:
            with self.subTest(key=key):
                self.assertEqual(correlate(self.rows, [self.boundaries[0] | {key: value}])['samples'], [])

    def test_runtime_is_bound_to_process(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['process_uuid'] = 'other'
        self.assertEqual(correlate(rows, self.boundaries)['samples'], [])
        rows = self.rows + [self.row(4, 'codex_models_manager::manager', 'evaluating cache eligibility client_version="0.153.1"')]
        self.assertEqual(correlate(rows, self.boundaries)['samples'], [])

    def test_wrong_target_cannot_supply_threshold(self):
        rows = copy.deepcopy(self.rows)
        rows[1]['target'] = 'codex_core::session::handlers'
        self.assertEqual(correlate(rows, self.boundaries)['samples'], [])

    def test_skill_budget_is_not_compaction_threshold(self):
        rows = copy.deepcopy(self.rows)
        rows[1]['feedback_log_body'] = rows[1]['feedback_log_body'].replace('auto_compact_scope_limit=Some(244800)', 'budget_limit=5440')
        self.assertEqual(correlate(rows, self.boundaries)['samples'], [])

    def test_body_scope_is_not_mislabeled_total(self):
        rows = copy.deepcopy(self.rows)
        rows[1]['feedback_log_body'] = rows[1]['feedback_log_body'].replace('scope=Total', 'scope=BodyAfterPrefix')
        self.assertEqual(correlate(rows, self.boundaries)['samples'], [])

    def test_retries_and_duplicate_boundaries_count_once(self):
        result = correlate(self.rows * 2, self.boundaries * 2)
        self.assertEqual(len(result['samples']), 1)

    def test_conflicting_limits_fail_closed(self):
        extra = self.rows[1] | {'feedback_log_body': self.rows[1]['feedback_log_body'].replace('Some(244800)', 'Some(240000)')}
        result = correlate(self.rows + [extra], self.boundaries)
        self.assertEqual(result['samples'], [])
        self.assertEqual(result['conflicting_turns_excluded'], 1)

    def test_manual_compaction_not_automatic(self):
        rows = copy.deepcopy(self.rows)
        rows[2]['feedback_log_body'] = rows[2]['feedback_log_body'].replace('reason=ContextLimit', 'reason=Manual')
        self.assertEqual(correlate(rows, self.boundaries)['samples'], [])
