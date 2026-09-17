"""Offline M4 experiments. Supplied provenance is not independently certified.

Only factual, chosen actions are scored. These reports never activate a policy.
"""
from collections import defaultdict
import math
import statistics

from .ledger import timestamp

GROUP = ('task_class', 'runtime_version', 'capability_revision', 'quota_epoch')


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def lower_bound(successes, count):
    """95% Wilson lower bound; descriptive, not a guarantee under selection bias."""
    z = 1.959963984540054
    p = successes / count
    return (p + z*z/(2*count) - z*math.sqrt(p*(1-p)/count + z*z/(4*count*count))) / (1 + z*z/count)


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered)*fraction)-1)]


def observations(rows):
    """Deduplicate task IDs and reject counterfactual, malformed or post-result predictions."""
    unique = {}
    for raw in rows:
        row = dict(raw)
        allowed = set(GROUP) | {'task_id', 'model_id', 'effort', 'currency', 'source',
            'chosen', 'evidence_kind', 'predicted_at', 'observed_at', 'status', 'success',
            'cost', 'duration_ms', 'total_tokens', 'duration_interval_ms', 'token_interval'}
        if set(row)-allowed:
            raise ValueError('Only projected observation fields accepted')
        for key in (*GROUP, 'task_id', 'model_id', 'effort', 'currency', 'source'):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError('Explicit observation identity, group and provenance required')
        if row.get('chosen') is not True or row.get('evidence_kind') not in {'real', 'synthetic'}:
            raise ValueError('Only explicitly chosen, provenance-labeled observations accepted')
        row['predicted_at'] = timestamp(row.get('predicted_at'))
        row['observed_at'] = timestamp(row.get('observed_at'))
        if row['predicted_at'] >= row['observed_at']:
            raise ValueError('Prediction must precede outcome')
        if row.get('status') not in {'completed', 'failed', 'timeout', 'cancelled'}:
            raise ValueError('Unknown observation status')
        if row.get('success') is not None and type(row['success']) is not bool:
            raise ValueError('Explicit quality label required')
        if row['status'] == 'failed' and row.get('success') is True:
            raise ValueError('Failed task cannot carry a successful outcome')
        if row['status'] in {'timeout', 'cancelled'} and row.get('success') is not None:
            raise ValueError('Censored quality must remain unknown')
        for key in ('cost', 'duration_ms', 'total_tokens'):
            if row.get(key) is not None and not number(row[key]):
                raise ValueError('Invalid observed measurement')
        for key in ('duration_interval_ms', 'token_interval'):
            interval = row.get(key)
            if interval is not None and (not isinstance(interval, list) or len(interval) != 2
                    or not all(number(v) for v in interval) or interval[0] > interval[1]):
                raise ValueError('Invalid pre-task interval')
        previous = unique.get(row['task_id'])
        if previous is not None and previous != row:
            raise ValueError('Conflicting task or counterfactual outcome')
        unique[row['task_id']] = row
    return sorted(unique.values(), key=lambda row: (row['observed_at'], row['task_id']))


def audit(rows, *, split_at, quality_floor=.9, minimum_samples=30, latency_budget_ms=None):
    """Time-split descriptive selection and coverage, segregated by deployment context.

    Test rows must have been predicted after the cutoff. No off-policy evaluation
    is possible for actions absent from the test data; no release pass is inferred.
    """
    split_at = timestamp(split_at)
    if not number(quality_floor) or not 0 < quality_floor <= 1:
        raise ValueError('Invalid quality floor')
    if type(minimum_samples) is not int or minimum_samples < 10:
        raise ValueError('At least ten observations required by experimental policy')
    if latency_budget_ms is not None and not number(latency_budget_ms):
        raise ValueError('Invalid latency budget')
    rows = observations(rows)
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in GROUP) + (row['currency'], row['evidence_kind'])].append(row)
    reports = []
    for key, group in sorted(groups.items()):
        train = [r for r in group if r['observed_at'] < split_at]
        test = [r for r in group if r['predicted_at'] >= split_at]
        candidates = []
        for action in sorted({(r['model_id'], r['effort']) for r in train}):
            samples = [r for r in train if (r['model_id'], r['effort']) == action]
            labels = [r['success'] for r in samples if r.get('success') is not None]
            costs = [r['cost'] for r in samples if r.get('cost') is not None]
            durations = [r['duration_ms'] for r in samples if r.get('duration_ms') is not None]
            lcb = lower_bound(sum(labels), len(labels)) if labels else None
            p80 = percentile(durations, .8) if durations else None
            # Missing/censored labels cannot be silently removed to qualify an action.
            eligible = (len(samples) >= minimum_samples and len(labels) == len(samples)
                        and len(costs) == len(samples) and lcb >= quality_floor
                        and (latency_budget_ms is None or (len(durations) == len(samples)
                             and p80 <= latency_budget_ms)))
            candidates.append({'model_id': action[0], 'effort': action[1], 'sample_count': len(samples),
                'quality_sample_count': len(labels), 'success_lcb': lcb,
                'mean_cost': statistics.mean(costs) if costs else None,
                'p80_duration_ms': p80, 'eligible': eligible})
        eligible = sorted((c for c in candidates if c['eligible']),
                          key=lambda c: (c['mean_cost'], c['model_id'], c['effort']))
        selected = eligible[0] if eligible else None
        matching = [r for r in test if selected and (r['model_id'], r['effort']) ==
                    (selected['model_id'], selected['effort'])]
        reports.append({'group': dict(zip((*GROUP, 'currency', 'evidence_kind'), key)),
            'train_count': len(train), 'test_count': len(test),
            'cross_cutoff_excluded': len(group)-len(train)-len(test),
            'candidates': candidates, 'experimental_selection': selected,
            'fallback': None if selected else 'EXISTING_EXPLICIT_POLICY',
            'test_factual_match_count': len(matching),
            'test_factual_success_count': sum(r.get('success') is True for r in matching),
            'test_factual_quality_count': sum(r.get('success') is not None for r in matching),
            'counterfactual_quality': None, 'baseline_improvement': None,
            'coverage': coverage(test), 'recalibration': recalibration(train, test, minimum_samples)})
    return {'status': 'OFFLINE_EXPERIMENT', 'split_at': split_at, 'groups': reports,
            'observation_count': len(rows), 'production_ready': False, 'automatic_switch': False,
            'limitations': ['Source provenance is supplied, not certified.',
                'Wilson bounds do not eliminate selection bias or distribution shift.',
                'Time-split factual matches do not prove improvement over a baseline.',
                'Independent real baseline evaluation is required before activation.']}


def coverage(rows):
    """Score pre-recorded intervals by model/effort and UTC day, within a group."""
    groups = defaultdict(list)
    for row in rows:
        groups[(row['model_id'], row['effort'], row['observed_at'][:10])].append(row)
    result = []
    histories = defaultdict(list)
    for (model, effort, day), group in sorted(groups.items()):
        metrics = {}
        for name, interval_key, value_key in [('duration', 'duration_interval_ms', 'duration_ms'),
                                               ('tokens', 'token_interval', 'total_tokens')]:
            pairs = [r for r in group if r['status'] == 'completed'
                     and r.get(interval_key) is not None and r.get(value_key) is not None]
            hits = [r[interval_key][0] <= r[value_key] <= r[interval_key][1] for r in pairs]
            errors = [r[value_key] - statistics.mean(r[interval_key]) for r in pairs]
            history = histories[(model, effort, name)]
            history.extend(zip(hits, errors))
            del history[:-200]
            recent = [hit for hit, _ in history[-10:]]
            rolling_errors = [error for _, error in history]
            drift = len(recent) == 10 and sum(recent) < 8
            median_shift = len(rolling_errors) >= 20 and abs(statistics.median(rolling_errors[-10:]) -
                statistics.median(rolling_errors[:-10])) > max(1, 2*statistics.median(abs(e) for e in rolling_errors[:-10]))
            metrics[name] = {'sample_count': len(pairs), 'hits': sum(hits),
                'empirical_coverage': sum(hits)/len(hits) if hits else None,
                'median_signed_error': statistics.median(errors) if errors else None,
                'drift_detected': drift or median_shift, 'rolling_sample_count': len(history),
                'action': 'RESET_BEFORE_RETRAINING' if drift or median_shift else 'INSPECT',
                'excluded_count': len(group)-len(pairs), 'coverage_guarantee': False}
        result.append({'model_id': model, 'effort': effort, 'utc_day': day, 'metrics': metrics})
    return result


def recalibration(train, test, minimum_samples):
    """Evaluate empirical widening against unchanged intervals on identical test rows."""
    results = []
    for action in sorted({(r['model_id'], r['effort']) for r in train}):
        for metric, interval_key, value_key in [('duration', 'duration_interval_ms', 'duration_ms'),
                                                ('tokens', 'token_interval', 'total_tokens')]:
            def pairs(rows):
                return [r for r in rows if (r['model_id'], r['effort']) == action
                        and r['status'] == 'completed' and r.get(interval_key) is not None
                        and r.get(value_key) is not None]
            training, testing = pairs(train), pairs(test)
            residuals = [max(r[interval_key][0]-r[value_key], r[value_key]-r[interval_key][1], 0)
                         for r in training]
            correction = percentile(residuals, .8) if len(training) >= minimum_samples else None
            baseline_hits = corrected_hits = 0
            widths = []
            for r in testing:
                low, high = r[interval_key]
                baseline_hits += low <= r[value_key] <= high
                if correction is not None:
                    low, high = max(0, low-correction), high+correction
                    corrected_hits += low <= r[value_key] <= high
                    widths.append(high-low)
            results.append({'model_id': action[0], 'effort': action[1], 'metric': metric,
                'train_count': len(training), 'test_count': len(testing), 'empirical_widening': correction,
                'baseline_coverage': baseline_hits/len(testing) if testing else None,
                'candidate_coverage': corrected_hits/len(testing) if testing and correction is not None else None,
                'candidate_mean_width': statistics.mean(widths) if widths else None,
                'activated': False, 'coverage_guarantee': False})
    return results
