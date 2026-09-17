"""Read-only native boundary inventory; never infer an exact compaction limit."""
import hashlib
import json
import os
from pathlib import Path
import stat


def inventory(paths, *, workspace):
    workspace = Path(workspace).resolve()
    observations = {}
    files = set()
    incomplete = 0
    for path in paths:
        # Open before checking file type, so FIFOs cannot block the inspection.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise ValueError('Expected an owned regular transcript file')
            if info.st_size > 256 * 1024 * 1024:
                raise ValueError('Transcript exceeds inventory size limit')
            identity = (info.st_dev, info.st_ino)
            if identity in files:
                continue
            files.add(identity)
            session = version = turn = model = active = None
            bound = False
            ordinal = 0
            # Read only the prefix present at open, even while a task appends records.
            remaining = info.st_size
            while remaining:
                raw = stream.readline(remaining)
                remaining -= len(raw)
                if not raw or not raw.endswith(b'\n'):
                    incomplete += 1
                    break
                try:
                    row = json.loads(raw)
                except ValueError:
                    raise ValueError('Malformed complete transcript record') from None
                if not isinstance(row, dict) or not isinstance(row.get('payload'), dict):
                    raise ValueError('Invalid transcript record shape')
                kind, payload = row.get('type'), row['payload']
                if kind == 'session_meta':
                    if session is not None:
                        raise ValueError('Repeated transcript session identity')
                    session, version = payload.get('id'), payload.get('cli_version')
                    if not all(isinstance(v, str) and v for v in (session, version)):
                        raise ValueError('Missing transcript session/runtime identity')
                elif kind == 'turn_context':
                    turn, model = payload.get('turn_id'), payload.get('model')
                    cwd = payload.get('cwd')
                    bound = isinstance(cwd, str) and Path(cwd).is_absolute() and Path(cwd).resolve() == workspace
                    active = None
                elif kind == 'event_msg' and payload.get('type') == 'task_started':
                    turn = model = active = None
                    bound = False
                elif kind == 'token_usage_record':
                    usage = payload.get('usage')
                    if (session and turn and bound and payload.get('thread_id') == session
                            and payload.get('turn_id') == turn):
                        value = usage.get('total_tokens') if isinstance(usage, dict) else None
                        active = value if type(value) is int and value >= 0 else None
                elif (kind in {'compacted', 'context_compaction'} or
                      kind == 'event_msg' and payload.get('type') == 'context_compacted'):
                    ordinal += 1
                    if session is None:
                        raise ValueError('Boundary precedes transcript identity')
                    if bound and isinstance(turn, str) and turn:
                        event_id = hashlib.sha256(json.dumps([session, ordinal]).encode()).hexdigest()
                        item = {'event_id': event_id, 'runtime_version': version,
                                'model': model if isinstance(model, str) and model else None,
                                'preceding_active_context_tokens': active,
                                'trigger': 'unknown', 'limit_scope': 'unknown',
                                'observed_compact_limit': None, 'verified_real': False}
                        if event_id in observations and observations[event_id] != item:
                            raise ValueError('Conflicting copies of a boundary observation')
                        observations[event_id] = item
                    # Never reuse pre-compaction usage for another boundary.
                    active = None
            if session is None:
                raise ValueError('Missing transcript identity')
    rows = sorted(observations.values(), key=lambda r: r['event_id'])
    groups = {}
    for row in rows:
        key = (row['runtime_version'], row['model'])
        group = groups.setdefault(key, {'runtime_version': key[0], 'model': key[1],
                                       'compaction_records': 0, 'preceding_active_records': 0})
        group['compaction_records'] += 1
        group['preceding_active_records'] += row['preceding_active_context_tokens'] is not None
    return {'files_scanned': len(files), 'incomplete_tails_ignored': incomplete,
            'observations': rows, 'groups': sorted(groups.values(), key=lambda g: (g['runtime_version'], g['model'] or '')),
            'qualifying_known_scope_numeric_thresholds': 0, 'configuration_changed': False,
            'note': 'Compaction records may include aliases. Preceding active usage is not an exact threshold; automatic trigger is unverified.'}
