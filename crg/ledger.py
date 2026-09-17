"""Private projected event ledger. No transcript storage or background collection."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from .durable import private_directory

TOKENS = ('input_tokens','output_tokens','cached_input_tokens','reasoning_output_tokens','total_tokens')
FIELDS = ('observed_at','source_kind','source_scope','account_fingerprint','workspace_id','thread_id',
          'turn_id','model_id','effort',*TOKENS,'active_context_tokens','duration_ms','completion_state')


def timestamp(value):
    if not isinstance(value,str): raise ValueError('Timezone-aware ISO timestamp required')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None: raise ValueError('Timezone required')
    return parsed.astimezone(timezone.utc).isoformat()


def identity(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def nonnegative(value):
    if value is not None and (type(value) is not int or value < 0): raise ValueError('Nonnegative integer or null required')
    return value


def connect(path):
    path=Path(path).absolute()
    private_directory(path.parent)
    if path.is_symlink(): raise ValueError('Symlink ledger refused')
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);os.close(fd)
    if path.stat().st_mode & 0o077 or path.stat().st_uid!=os.getuid(): raise ValueError('Ledger must be private (0600)')
    db=sqlite3.connect(path, timeout=10)
    db.row_factory=sqlite3.Row
    version=db.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0,1):db.close();raise ValueError('Unknown ledger schema')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA user_version=1')
    return db


class Ledger:
    def __init__(self,path):
        self.db=connect(path)
        columns=','.join(f'{key} '+('INTEGER' if key in TOKENS+('active_context_tokens','duration_ms') else 'TEXT') for key in FIELDS)
        self.db.execute(f'CREATE TABLE IF NOT EXISTS ledger_event(event_id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,payload_version INTEGER NOT NULL,{columns})')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_ledger_time ON ledger_event(observed_at)')
        self.db.execute('CREATE INDEX IF NOT EXISTS idx_ledger_model ON ledger_event(model_id,effort,observed_at)')
        self.db.execute('CREATE TABLE IF NOT EXISTS counter_observation(event_id TEXT PRIMARY KEY, counter_key TEXT NOT NULL, observed_at TEXT NOT NULL, raw_tokens TEXT NOT NULL, reset_detected INTEGER NOT NULL)')
        self.db.commit()
    def close(self):self.db.close()
    def add(self,event):
        allowed=set(FIELDS)|{'source_event_id','counter_semantics'}
        if not isinstance(event,dict) or set(event)-allowed: raise ValueError('Only projected ledger fields accepted')
        event=dict(event)
        event['observed_at']=timestamp(event.get('observed_at'))
        for field in ('source_event_id','source_kind','source_scope','completion_state'):
            if not isinstance(event.get(field),str) or not event[field]:raise ValueError('Missing source identity/scope/state')
        if event['completion_state'] not in {'completed','failed','cancelled','timeout','interrupted','superseded','observed'}:raise ValueError('Unknown completion state')
        for key in TOKENS+('active_context_tokens','duration_ms'):nonnegative(event.get(key))
        semantics=event.get('counter_semantics')
        if semantics not in {'per_event','cumulative','unknown'}:raise ValueError('Explicit counter semantics required')
        ident=identity([event.get(k) for k in ('source_kind','source_scope','account_fingerprint','workspace_id','thread_id','source_event_id')])
        payload_hash=identity(event)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            existing=self.db.execute('SELECT payload_hash FROM ledger_event WHERE event_id=?',(ident,)).fetchone()
            if existing:
                if existing[0]!=payload_hash:raise ValueError('Conflicting duplicate event')
                return ident
            projected=dict(event)
            if semantics=='unknown':
                for key in TOKENS:projected[key]=None
            if semantics=='cumulative':
                counter=identity([event.get(k) for k in ('source_kind','source_scope','account_fingerprint','workspace_id','thread_id','model_id')])
                previous=self.db.execute('SELECT * FROM counter_observation WHERE counter_key=? ORDER BY observed_at DESC LIMIT 1',(counter,)).fetchone()
                if previous and previous['observed_at']>=event['observed_at']:raise ValueError('Out-of-order cumulative observation')
                raw={key:event.get(key) for key in TOKENS}
                old=json.loads(previous['raw_tokens']) if previous else {}
                reset=any(value is not None and old.get(key) is not None and value<old[key] for key,value in raw.items())
                for key,value in raw.items():
                    projected[key]=value-old[key] if previous and not reset and value is not None and old.get(key) is not None else None
                self.db.execute('INSERT INTO counter_observation VALUES(?,?,?,?,?)',(ident,counter,event['observed_at'],json.dumps(raw),int(reset)))
            self.db.execute(f'INSERT INTO ledger_event(event_id,payload_hash,payload_version,{",".join(FIELDS)}) VALUES({",".join("?" for _ in range(len(FIELDS)+3))})',
                            (ident,payload_hash,1,*(projected.get(key) for key in FIELDS)))
        return ident
    def usage(self,scope,start,end):
        start,end=timestamp(start),timestamp(end)
        if start>=end:raise ValueError('Invalid time interval')
        rows=self.db.execute('SELECT total_tokens FROM ledger_event WHERE source_scope=? AND observed_at>=? AND observed_at<?',(scope,start,end)).fetchall()
        known=[row[0] for row in rows if row[0] is not None]
        return {'scope':scope,'source':'local projected ledger; excludes unobserved devices/cloud tasks',
                'time_basis':'UTC observed_at, half-open interval','start':start,'end':end,
                'reset_semantics':'counter decreases establish new unknown baseline; history retained',
                'known_total_tokens':sum(known) if known else None,'sample_count':len(rows),
                'known_samples':len(known),'unknown_samples':len(rows)-len(known),
                'coverage':'partial' if len(known)!=len(rows) or not rows else 'recorded_events_only'}
