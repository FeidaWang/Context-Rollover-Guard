"""Opt-in, read-only validation of a separately generated runtime schema.

Run: python -m tests.live_schema --schema /path/to/evidence/schema
This is not part of the offline suite and never generates schema or invokes Codex.
"""
import argparse
import json
from pathlib import Path
from crg.appserver import ProtocolSchema
from crg.capability_probe import inspect_schema

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--schema', type=Path, required=True)
    args = parser.parse_args()
    schema = ProtocolSchema(args.schema)
    if schema.runtime_version == 'synthetic-offline-v1':
        parser.error('Supply live generated evidence, not the synthetic fixture')
    result = inspect_schema(args.schema)
    assert all(result['methods'].values()), result
    assert all(result['hooks_supported'].values()), result
    assert result['token_usage_supported'], result
    assert result['client_user_message_id_supported'], result
    print(json.dumps({'evidence': 'STATIC_REVIEW', 'runtime_version': schema.runtime_version, 'schema_contract': result}))
