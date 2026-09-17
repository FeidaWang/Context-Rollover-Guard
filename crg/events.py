"""Version-one content-free analytical contracts; never recovery authority."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math

TOKENS = ('input_tokens', 'output_tokens', 'cached_input_tokens',
          'reasoning_output_tokens', 'total_tokens')
KINDS = {
    'context': {'active_context_tokens', 'window_tokens'},
    'usage': {*TOKENS, 'semantics', 'generation', 'request_id', 'parent_id',
              'aggregation', 'subset_contract', 'zero_origin_at'},
    'quota': {'bucket_id', 'limit_id', 'policy_epoch', 'used_percent', 'reset_at'},
    'timing': {'wall_ms', 'active_ms', 'acceptance_ms', 'process_id', 'complete'},
    'outcome': {'status', 'accepted', 'evidence_kind'},
    'prediction': {'target', 'lower', 'upper', 'intent_hash', 'predictor_version'},
    'cost': {'amount', 'currency', 'price_version', 'estimated'},
}
META = {'schema_version', 'kind', 'observation_id', 'fact_id', 'revision', 'source',
        'adapter_version', 'scope', 'account_id', 'workspace_id', 'thread_id',
        'observed_at', 'received_at', 'quality', 'data'}


def instant(value):
    if not isinstance(value, str):
        raise ValueError('Timezone-aware timestamp required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone required')
    return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds')


def number(value, *, integer=False):
    if value is not None and (type(value) not in ((int,) if integer else (int, float))
                              or not math.isfinite(value) or value < 0 or (integer and value > 2**63-1)):
        raise ValueError('Finite nonnegative number or null required')
    return value


@dataclass(frozen=True)
class Observation:
    """Construction validates; serialization returns a detached allowlisted value."""
    payload: dict

    def __post_init__(self):
        import json
        row = json.loads(json.dumps(self.payload, allow_nan=False))
        if set(row) - META or type(row.get('schema_version')) is not int or row['schema_version'] != 1:
            raise ValueError('Unknown observation contract')
        if row.get('kind') not in KINDS:
            raise ValueError('Unknown semantic object')
        for key in ('observation_id', 'fact_id', 'source', 'adapter_version'):
            if not isinstance(row.get(key), str) or not row[key] or len(row[key]) > 256:
                raise ValueError('Bounded source identity required')
        if row.get('scope') not in {'local', 'account', 'unknown'} or row.get('quality') not in {'verified', 'synthetic', 'unverified'}:
            raise ValueError('Explicit scope and quality required')
        for key in ('account_id', 'workspace_id', 'thread_id'):
            if row.get(key) is not None and (not isinstance(row[key], str) or not row[key] or len(row[key]) > 256):
                raise ValueError('Invalid scoped identity')
        if type(row.get('revision')) is not int or row['revision'] < 0:
            raise ValueError('Revision required')
        for key in ('observed_at', 'received_at'):
            row[key] = instant(row.get(key))
        data = row.get('data')
        if not isinstance(data, dict) or set(data) - KINDS[row['kind']]:
            raise ValueError('Fields cannot be exchanged between semantic objects')
        for key in set(data) & {*TOKENS, 'active_context_tokens', 'window_tokens', 'wall_ms', 'active_ms', 'acceptance_ms'}:
            number(data[key], integer=True)
        for key in set(data) & {'used_percent', 'amount', 'lower', 'upper'}:
            number(data[key])
        if data.get('used_percent') is not None and data['used_percent'] > 100:
            raise ValueError('Invalid percentage')
        for key in ('accepted', 'estimated', 'complete'):
            if key in data and data[key] is not None and type(data[key]) is not bool:
                raise ValueError('Boolean or null required')
        for key in ('zero_origin_at', 'reset_at'):
            if data.get(key) is not None:
                data[key] = instant(data[key])
        if row['kind'] == 'usage':
            if data.get('semantics') not in {'request_increment', 'cumulative_snapshot', 'account_daily', 'unknown'}:
                raise ValueError('Usage semantics required')
            if data.get('aggregation') not in {'exclusive', 'includes_children', 'unknown'}:
                raise ValueError('Parent aggregation contract required')
            if data.get('subset_contract') not in {'input_output_include_subsets', 'unknown'}:
                raise ValueError('Subset contract required')
            if data['semantics'] == 'cumulative_snapshot' and not isinstance(data.get('generation'), str):
                raise ValueError('Counter generation required')
            if data['subset_contract'] == 'input_output_include_subsets':
                for sub, whole in (('cached_input_tokens', 'input_tokens'), ('reasoning_output_tokens', 'output_tokens')):
                    if data.get(sub) is not None and data.get(whole) is not None and data[sub] > data[whole]:
                        raise ValueError('Subset exceeds whole')
                if data.get('input_tokens') is not None and data.get('output_tokens') is not None:
                    total = data['input_tokens'] + data['output_tokens']
                    if data.get('total_tokens') is not None and data['total_tokens'] != total:
                        raise ValueError('Inconsistent verified total')
                    data['total_tokens'] = total
        object.__setattr__(self, 'payload', row)

    def to_dict(self):
        import copy
        return copy.deepcopy(self.payload)

    def exact_usage(self):
        row = self.payload
        if row['kind'] != 'usage':
            raise ValueError('Only usage objects contribute to usage totals')
        data = row['data']
        if (row['scope'] == 'unknown' or row['quality'] == 'unverified'
                or data['aggregation'] != 'exclusive' or data.get('parent_id')
                or data['semantics'] == 'unknown'):
            return None
        return data.get('total_tokens')


def project(raw):
    """Adapter boundary drops transcript/unknown fields before validation or storage."""
    row = {key: value for key, value in raw.items() if key in META}
    kind = row.get('kind')
    if kind in KINDS and isinstance(row.get('data'), dict):
        row['data'] = {key: value for key, value in row['data'].items() if key in KINDS[kind]}
    return Observation(row)
