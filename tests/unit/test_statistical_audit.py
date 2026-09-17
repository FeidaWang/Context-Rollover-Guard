import unittest
from crg.statistical_audit import audit, observations


def row(i=0, **changes):
    return dict(task_id=str(i), task_class='code', runtime_version='fixture-v1',
        capability_revision='fixture-c1', quota_epoch='q1', model_id='fixture-model', effort='high',
        currency='fixture-unit', source='fixture', evidence_kind='synthetic', chosen=True,
        predicted_at='2026-01-01T00:00:00Z', observed_at='2026-01-01T01:00:00Z',
        status='completed', success=True, cost=1, duration_ms=100, total_tokens=200,
        duration_interval_ms=[80, 120], token_interval=[100, 300]) | changes


class StatisticalAudit(unittest.TestCase):
    def run_audit(self, rows, **kwargs):
        return audit(rows, split_at='2026-01-02T00:00:00Z', **kwargs)

    def test_sparse_fallback_and_quality_bound(self):
        report = self.run_audit([row(i) for i in range(30)])
        self.assertIsNone(report['groups'][0]['experimental_selection'])  # 30/30 LCB < .9
        report = self.run_audit([row(i) for i in range(40)])
        self.assertIsNotNone(report['groups'][0]['experimental_selection'])
        self.assertFalse(report['production_ready'])
        self.assertIsNone(report['groups'][0]['baseline_improvement'])

    def test_only_observed_cost_and_latency(self):
        rows = [row(i, model_id='cheap', cost=.5, duration_ms=500) for i in range(40)]
        rows += [row(100+i, model_id='fast', cost=2) for i in range(40)]
        group = self.run_audit(rows, latency_budget_ms=200)['groups'][0]
        self.assertEqual(group['experimental_selection']['model_id'], 'fast')
        rows = [row(i, cost=None) for i in range(40)]
        self.assertIsNone(self.run_audit(rows)['groups'][0]['experimental_selection'])

    def test_counterfactual_and_conflicting_replay_rejected(self):
        for rows in ([row(), row(model_id='unchosen')], [row(chosen=False)]):
            with self.assertRaises(ValueError): observations(rows)
        self.assertEqual(len(observations([row(), row()])), 1)

    def test_no_future_leakage(self):
        rows = [row(i, predicted_at='2026-01-02T01:00:00Z', observed_at='2026-01-03T00:00:00Z') for i in range(40)]
        rows.append(row(50, observed_at='2026-01-03T00:00:00Z'))
        group = self.run_audit(rows)['groups'][0]
        self.assertEqual(group['train_count'], 0)
        self.assertEqual(group['test_count'], 40)
        self.assertEqual(group['cross_cutoff_excluded'], 1)
        self.assertIsNone(group['experimental_selection'])
        with self.assertRaises(ValueError): observations([row(predicted_at='2026-01-04T00:00:00Z')])

    def test_groups_never_mix(self):
        rows = [row()]
        for i, field in enumerate(('task_class','runtime_version','capability_revision','quota_epoch','currency','evidence_kind')):
            rows.append(row(i+1, **{field:'real' if field=='evidence_kind' else 'different'}))
        self.assertEqual(len(self.run_audit(rows)['groups']), 7)

    def test_censored_and_unknown_cannot_qualify(self):
        for changes in ({'success':None}, {'status':'timeout','success':None}):
            rows = [row(i) for i in range(40)] + [row(50, **changes)]
            self.assertIsNone(self.run_audit(rows)['groups'][0]['experimental_selection'])

    def test_coverage_and_misses_by_day(self):
        rows = [row(i, predicted_at='2026-01-02T01:00:00Z', observed_at='2026-01-03T00:00:00Z', duration_ms=500) for i in range(10)]
        rows += [row(20, predicted_at='2026-01-03T01:00:00Z', observed_at='2026-01-04T00:00:00Z')]
        report = self.run_audit(rows)['groups'][0]['coverage']
        self.assertEqual(len(report), 2)
        self.assertTrue(report[0]['metrics']['duration']['drift_detected'])
        self.assertFalse(report[0]['metrics']['tokens']['drift_detected'])
        self.assertEqual(report[1]['metrics']['duration']['empirical_coverage'], 1)

    def test_censored_coverage_excluded(self):
        rows = [row(predicted_at='2026-01-02T01:00:00Z', observed_at='2026-01-03T00:00:00Z', status='timeout', success=None)]
        metric = self.run_audit(rows)['groups'][0]['coverage'][0]['metrics']['duration']
        self.assertEqual(metric['sample_count'], 0)
        self.assertIsNone(metric['empirical_coverage'])

    def test_invalid_numbers_and_intervals(self):
        for changes in ({'cost':float('nan')}, {'duration_ms':True}, {'token_interval':[2,1]}, {'success':1}):
            with self.assertRaises(ValueError): observations([row(**changes)])
        for kwargs in ({'quality_floor':float('nan')}, {'minimum_samples':True}, {'latency_budget_ms':-1}):
            with self.assertRaises(ValueError): self.run_audit([], **kwargs)

    def test_recalibration_uses_training_only_and_same_test_pairs(self):
        training = [row(i, duration_ms=140) for i in range(40)]
        test = [row(50, predicted_at='2026-01-02T01:00:00Z', observed_at='2026-01-03T00:00:00Z', duration_ms=140)]
        metric = self.run_audit(training+test)['groups'][0]['recalibration'][0]
        self.assertEqual(metric['empirical_widening'], 20)
        self.assertEqual(metric['baseline_coverage'], 0)
        self.assertEqual(metric['candidate_coverage'], 1)
        test[0]['duration_ms'] = 1000
        metric = self.run_audit(training+test)['groups'][0]['recalibration'][0]
        self.assertEqual(metric['empirical_widening'], 20)
        self.assertEqual(metric['candidate_coverage'], 0)
        self.assertFalse(metric['activated'])

    def test_misses_accumulate_across_days(self):
        rows = [row(i, predicted_at='2026-01-02T00:00:00Z',
                    observed_at=f'2026-01-{i+3:02d}T00:00:00Z', duration_ms=500) for i in range(10)]
        report = self.run_audit(rows)['groups'][0]['coverage']
        self.assertFalse(report[0]['metrics']['duration']['drift_detected'])
        self.assertTrue(report[-1]['metrics']['duration']['drift_detected'])
        self.assertEqual(report[-1]['metrics']['duration']['rolling_sample_count'], 10)

    def test_raw_payload_and_contradictory_success_refused(self):
        for changes in ({'prompt':'private content'}, {'status':'failed','success':True}):
            with self.assertRaises(ValueError): observations([row(**changes)])
