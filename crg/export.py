"""Previewable, numeric-only export. No upload or recovery cleanup API."""
import hashlib
import json
import os
from pathlib import Path
import secrets
from .events import Observation, TOKENS
from .durable import private_directory


def preview(observations):
    aliases, rows = {}, []
    for item in observations:
        row = (item if isinstance(item, Observation) else Observation(item)).to_dict()
        key = (row.get('account_id'), row.get('workspace_id'), row.get('thread_id'))
        alias = aliases.setdefault(key, secrets.token_hex(12))
        # No arbitrary source/model/version strings pass this contract.
        numeric = {k: row['data'][k] for k in (*TOKENS, 'wall_ms', 'active_ms', 'acceptance_ms', 'used_percent') if k in row['data']}
        rows.append({'alias': alias, 'schema_version': 1, 'kind': row['kind'],
                     'quality': row['quality'], 'scope': row['scope'], 'values': numeric})
    bundle = {'export_version': 1, 'records': rows,
              'privacy': 'Per-export aliases; numeric metadata can still be identifying. Review before sharing.'}
    encoded = json.dumps(bundle, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return {'bundle': bundle, 'sha256': hashlib.sha256(encoded).hexdigest()}


def write_approved(previewed, path, *, approved_sha256):
    encoded = json.dumps(previewed['bundle'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    if approved_sha256 != digest or previewed.get('sha256') != digest:
        raise ValueError('Exact preview approval required')
    bundle = previewed['bundle']
    if set(bundle) != {'export_version','records','privacy'} or type(bundle['export_version']) is not int or bundle['export_version'] != 1:
        raise ValueError('Unsupported export format')
    # Recheck typed boundary even if caller fabricated a preview object.
    from .events import KINDS, number
    import re
    if bundle['privacy'] != 'Per-export aliases; numeric metadata can still be identifying. Review before sharing.':
        raise ValueError('Unknown export metadata')
    for row in bundle['records']:
        if set(row) != {'alias','schema_version','kind','quality','scope','values'} or type(row['schema_version']) is not int or row['schema_version'] != 1:
            raise ValueError('Invalid export row')
        if (not isinstance(row['alias'],str) or not re.fullmatch('[0-9a-f]{24}',row['alias'])
                or row['kind'] not in KINDS or row['quality'] not in {'verified','synthetic','unverified'}
                or row['scope'] not in {'local','account','unknown'}):
            raise ValueError('Unreviewed string field')
        if set(row['values']) - set((*TOKENS,'wall_ms','active_ms','acceptance_ms','used_percent')):
            raise ValueError('Unknown export field')
        for key,value in row['values'].items(): number(value,integer=key!='used_percent')
    path = Path(path).absolute(); private_directory(path.parent)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd,'wb') as out:
        out.write(encoded+b'\n'); out.flush(); os.fsync(out.fileno())
    return {'written':True,'sha256':digest,'uploaded':False}


def interchange(observations, *, format='jsonl'):
    """Versioned numeric rows; each bundle has fresh deduplication identities."""
    import csv
    import io
    from .ledger import identity
    latest={}
    for item in observations:
        row=(item if isinstance(item,Observation) else Observation(item)).to_dict()
        key=identity([row.get(k) for k in ('source','adapter_version','scope','account_id','workspace_id','thread_id','kind','fact_id')])
        old=latest.get(key)
        if old and old['revision']==row['revision']:
            a={k:v for k,v in old.items() if k not in {'received_at','observation_id'}}
            b={k:v for k,v in row.items() if k not in {'received_at','observation_id'}}
            if a!=b:raise ValueError('Conflicting export fact revision')
        if old is None or old['revision']<row['revision']:latest[key]=row
    bundle=preview(list(latest.values()))['bundle']
    bundle_id=secrets.token_hex(12);rows=[]
    for row in bundle['records']:
        rows.append({'export_version':1,'bundle_id':bundle_id,'record_id':secrets.token_hex(12),
                     'cluster_id':row['alias'],'scope':row['scope'],'kind':row['kind'],'quality':row['quality'],
                     'token_unit':'tokens','time_unit':'milliseconds','quota_unit':'percentage_points',
                     **{key:row['values'].get(key) for key in (*TOKENS,'wall_ms','active_ms','acceptance_ms','used_percent')}})
    if format=='jsonl':return ''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows)
    if format!='csv':raise ValueError('Unsupported interchange format')
    out=io.StringIO()
    fields=['export_version','bundle_id','record_id','cluster_id','scope','kind','quality','token_unit','time_unit','quota_unit',*TOKENS,'wall_ms','active_ms','acceptance_ms','used_percent']
    writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    return out.getvalue()
