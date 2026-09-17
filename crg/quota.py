"""Account snapshots and quota epochs, separate from local token consumption."""
import json
import math
from .ledger import connect,identity,timestamp,nonnegative

FIELDS=('observed_at','source','account_fingerprint','bucket_id','used_percent','remaining_percent',
        'reset_at','window_seconds','raw_limit_units','unit_name','freshness_seconds')


class Quotas:
    def __init__(self,path):
        self.db=connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS quota_snapshot(snapshot_id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,account_key TEXT NOT NULL,bucket_id TEXT NOT NULL,observed_at TEXT NOT NULL,payload TEXT NOT NULL,epoch_id TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS quota_epoch(epoch_id TEXT PRIMARY KEY,account_key TEXT NOT NULL,bucket_id TEXT NOT NULL,started_at TEXT NOT NULL,reset_reason TEXT NOT NULL,previous_epoch_id TEXT,confidence TEXT NOT NULL)')
        self.db.commit()
    def close(self):self.db.close()
    def add(self,snapshot):
        allowed=set(FIELDS)|{'source_snapshot_id','authoritative_reset_id','user_confirmed_reset'}
        if not isinstance(snapshot,dict) or set(snapshot)-allowed:raise ValueError('Only projected quota fields accepted')
        row=dict(snapshot)
        for key in ('source','account_fingerprint','bucket_id','source_snapshot_id'):
            if not isinstance(row.get(key),str) or not row[key]:raise ValueError('Explicit source/account fingerprint/bucket identity required')
        row['observed_at']=timestamp(row.get('observed_at'))
        if row.get('reset_at') is not None:row['reset_at']=timestamp(row['reset_at'])
        for key in ('used_percent','remaining_percent'):
            value=row.get(key)
            if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100):raise ValueError('Invalid percentage')
        if row.get('used_percent') is not None:
            expected=100-row['used_percent']
            if row.get('remaining_percent') is not None and abs(row['remaining_percent']-expected)>1e-6:raise ValueError('Inconsistent percentages')
            row['remaining_percent']=expected
        for key in ('window_seconds','freshness_seconds','raw_limit_units'):nonnegative(row.get(key))
        if row.get('raw_limit_units') is not None and not row.get('unit_name'):raise ValueError('Authoritative units require a unit name')
        if 'user_confirmed_reset' in row and type(row['user_confirmed_reset']) is not bool:raise ValueError('Explicit reset confirmation must be boolean')
        reset=row.get('authoritative_reset_id')
        if reset is not None and (not isinstance(reset,str) or not reset):raise ValueError('Invalid authoritative reset identity')
        account=row['account_fingerprint'];bucket=row['bucket_id'];observed=row['observed_at']
        ident=identity([row['source'],account,bucket,row['source_snapshot_id']]);payload_hash=identity(row)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            existing=self.db.execute('SELECT * FROM quota_snapshot WHERE snapshot_id=?',(ident,)).fetchone()
            if existing:
                if existing['payload_hash']!=payload_hash:raise ValueError('Conflicting quota replay')
                return existing['epoch_id']
            previous=self.db.execute('SELECT * FROM quota_snapshot WHERE account_key=? AND bucket_id=? ORDER BY observed_at DESC LIMIT 1',(account,bucket)).fetchone()
            if previous and previous['observed_at']>=observed:raise ValueError('Out-of-order quota snapshot')
            epoch=previous['epoch_id'] if previous else None
            old=json.loads(previous['payload']) if previous else {}
            reason='INITIAL_OBSERVATION' if not previous else None;confidence='OBSERVED'
            if reset:
                reason='AUTHORITATIVE_RESET';confidence='SOURCE_CONFIRMED'
            elif (previous and old.get('reset_at') and old['observed_at']<old['reset_at']<=observed
                  and row['source']==old['source'] and row.get('used_percent') is not None
                  and old.get('used_percent') is not None and old['used_percent']-row['used_percent']>=10):
                reason='RESET_BOUNDARY_AND_DROP';confidence='INFERRED'
            elif row.get('user_confirmed_reset') is True:
                reason='USER_DECLARED_RESET';confidence='USER_CONFIRMED'
            if reason:
                new=identity([account,bucket,'reset',reset]) if reset else identity([ident,reason])
                found=self.db.execute('SELECT epoch_id FROM quota_epoch WHERE epoch_id=?',(new,)).fetchone()
                if not found:self.db.execute('INSERT INTO quota_epoch VALUES(?,?,?,?,?,?,?)',(new,account,bucket,observed,reason,epoch,confidence))
                elif new!=epoch:raise ValueError('Stale authoritative reset event')
                epoch=new
            self.db.execute('INSERT INTO quota_snapshot VALUES(?,?,?,?,?,?,?)',(ident,payload_hash,account,bucket,observed,json.dumps(row,sort_keys=True),epoch))
        return epoch
    def latest(self,account,bucket,*,at):
        at=timestamp(at)
        found=self.db.execute('SELECT * FROM quota_snapshot WHERE account_key=? AND bucket_id=? AND observed_at<=? ORDER BY observed_at DESC LIMIT 1',(account,bucket,at)).fetchone()
        if not found:return {'status':'UNKNOWN','sample_count':0,'bucket_id':bucket,'remaining_percent':None}
        from datetime import datetime
        row=json.loads(found['payload'])
        age=(datetime.fromisoformat(at)-datetime.fromisoformat(row['observed_at'])).total_seconds()
        fresh=row.get('freshness_seconds')
        stale=fresh is None or age>fresh
        return {'status':'STALE_OR_UNKNOWN_FRESHNESS' if stale else 'OBSERVED',
                'scope':'account fingerprint and bucket','source':row['source'],'observed_at':row['observed_at'],
                'age_seconds':age,'sample_count':1,'bucket_id':bucket,'epoch_id':found['epoch_id'],
                'remaining_percent':None if stale else row.get('remaining_percent'),
                'last_observed_remaining_percent':row.get('remaining_percent'),
                'tokens_remaining':None,'reset_at':row.get('reset_at'),
                'reset_semantics':'epochs preserve historical consumption; percentages are not token balances'}
