"""Join native numeric threshold logs to successful, identity-bound compactions.

Input messages are projected to numbers and identities only. Session creation versions
are deliberately not used: a later runtime can resume an older session.
"""
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .calibration import summarize


def correlate(logs, boundaries):
    versions = defaultdict(set)
    automatic = defaultdict(list)
    numeric = []
    for row in logs:
        body, target = row['feedback_log_body'] or '', row['target']
        process = row['process_uuid']
        if not process:
            continue
        if target == 'codex_models_manager::manager':
            match = re.search(r'evaluating cache eligibility client_version="([0-9][^"]*)"', body)
            if match:
                versions[process].add(match[1])
        auto_target = (target.startswith('codex_core::compact_remote') or target in {
            'feedback_tags', 'codex_skills_extension::render_observability',
            'codex_http_client::custom_ca', 'codex_http_client::request'})
        if auto_target and 'run_auto_compact{reason=ContextLimit ' in body:
            turn = re.search(r'\bturn\.id=([0-9a-f-]{36})\b', body)
            if turn:
                automatic[(process, row['thread_id'], turn[1])].append(row['ts'])
        if target == 'codex_core::session::turn' and ': post sampling token usage ' in body:
            prefix, suffix = body.rsplit(': post sampling token usage ', 1)
            fields = dict(re.findall(r'(\w+)=(\S+)', suffix))
            match = re.search(r'\bmodel=([^\s}]+)', prefix)
            limit = re.fullmatch(r'Some\(([1-9][0-9]*)\)', fields.get('auto_compact_scope_limit', ''))
            active = fields.get('total_usage_tokens', '')
            scoped = fields.get('auto_compact_scope_tokens', '')
            # Total is the only verified mapping to active_context_tokens in this adapter.
            if (match and limit and active.isdigit() and scoped == active
                    and fields.get('auto_compact_limit_scope') == 'Total'
                    and fields.get('token_limit_reached') == 'true'
                    and int(active) >= int(limit[1])):
                numeric.append({'process': process, 'thread': row['thread_id'],
                                'turn': fields.get('turn_id'), 'model': match[1],
                                'ts': row['ts'], 'active': int(active), 'limit': int(limit[1]),
                                'log_id': row['id']})
    accepted = {}
    conflicts = set()
    for record in numeric:
        version = versions[record['process']]
        if len(version) != 1:
            continue
        key = (record['process'], record['thread'], record['turn'])
        matches = [b for b in boundaries
                   if b['session'] == record['thread'] and b['turn'] == record['turn']
                   and b['model'] == record['model'] and record['ts'] <= b['ts'] <= record['ts'] + 600
                   and any(record['ts'] <= ts <= b['ts'] for ts in automatic[key])]
        if not matches:
            continue
        event = hashlib.sha256(json.dumps([record['thread'], record['turn']]).encode()).hexdigest()
        sample = {'event_id': event, 'model': record['model'], 'runtime_version': next(iter(version)),
                  'limit_scope': 'total', 'active_context_tokens': record['active'],
                  'observed_compact_limit': record['limit'], 'automatic_precompact': True,
                  'verified_real': True, 'source_log_id': record['log_id']}
        if event in accepted and any(accepted[event][k] != sample[k]
                                     for k in ('runtime_version', 'model', 'observed_compact_limit')):
            conflicts.add(event)
        accepted.setdefault(event, sample)  # at most one boundary per turn, even after retries
    samples = [accepted[key] for key in sorted(accepted) if key not in conflicts]
    return {'samples': samples, 'groups': summarize(samples),
            'numeric_limit_reached_records': len(numeric), 'conflicting_turns_excluded': len(conflicts),
            'configuration_changed': False,
            'note': 'Exact logged limits joined to automatic ContextLimit activity and completed native compactions. No warning outcomes inferred.'}


def collect(database, transcripts):
    database = Path(database)
    if database.is_symlink() or not database.is_file():
        raise ValueError('Expected existing native log database')
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        logs = [dict(row) for row in connection.execute(
            "SELECT id,ts,target,feedback_log_body,thread_id,process_uuid FROM logs "
            "WHERE target='codex_models_manager::manager' "
            "OR target='codex_core::session::turn' "
            "OR target LIKE 'codex_core::compact_remote%' "
            "OR (target IN ('feedback_tags','codex_skills_extension::render_observability',"
            "'codex_http_client::custom_ca','codex_http_client::request') "
            "AND feedback_log_body LIKE '%run_auto_compact{reason=ContextLimit %') ORDER BY ts,ts_nanos,id")]
    candidates = {row['thread_id'] for row in logs
                  if 'token_limit_reached=true' in (row['feedback_log_body'] or '')}
    boundaries = []
    for path in transcripts:
        path = Path(path)
        if not any(identity and identity in path.name for identity in candidates):
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('Expected regular native transcript')
        session = None
        context = {}
        with path.open('rb') as stream:
            for raw in stream:
                if not raw.endswith(b'\n'):
                    break
                row = json.loads(raw)
                payload = row.get('payload', {})
                if row.get('type') == 'session_meta':
                    if session is not None:
                        raise ValueError('Repeated session identity')
                    session = payload.get('id')
                elif row.get('type') == 'turn_context':
                    context = payload
                elif row.get('type') == 'compacted' and session in candidates:
                    boundaries.append({'session': session, 'turn': context.get('turn_id'),
                                       'model': context.get('model'),
                                       'ts': datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')).timestamp()})
    return correlate(logs, boundaries)
