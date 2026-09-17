"""Persist pre-task estimates and completed/censored observations, without inference."""
from datetime import datetime,timezone
import json
import math
import statistics
import uuid
from .ledger import connect,identity,timestamp,nonnegative


def quantile(values,fraction):
    ordered=sorted(values)
    return ordered[min(len(ordered)-1,int((len(ordered)-1)*fraction))]


class Estimates:
    def __init__(self,path):
        self.db=connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS task_prediction(prediction_id TEXT PRIMARY KEY,task_class TEXT NOT NULL,model_id TEXT NOT NULL,effort TEXT NOT NULL,runtime_version TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS task_observation(prediction_id TEXT PRIMARY KEY,observed_at TEXT NOT NULL,status TEXT NOT NULL,duration_ms INTEGER,total_tokens INTEGER,success INTEGER,payload_hash TEXT NOT NULL,score TEXT NOT NULL)')
        self.db.commit()
    def close(self):self.db.close()
    def begin(self,task_class,model_id,effort,runtime_version,*,prediction_id=None,at=None):
        for value in (task_class,model_id,effort,runtime_version):
            if not isinstance(value,str) or not value:raise ValueError('Explicit task/model/effort/runtime required')
        created=timestamp(at or datetime.now(timezone.utc).isoformat());ident=prediction_id or uuid.uuid4().hex
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            previous=self.db.execute('SELECT * FROM task_prediction WHERE prediction_id=?',(ident,)).fetchone()
            if previous:
                if [previous[k] for k in ('task_class','model_id','effort','runtime_version')]!=[task_class,model_id,effort,runtime_version]:raise ValueError('Conflicting prediction identity')
                return json.loads(previous['payload'])
            rows=self.db.execute('SELECT p.task_class,p.model_id,p.effort,o.* FROM task_observation o JOIN task_prediction p USING(prediction_id) WHERE p.runtime_version=? AND o.status="completed" AND o.observed_at<? ORDER BY o.observed_at DESC LIMIT 200',(runtime_version,created)).fetchall()
            current=datetime.fromisoformat(created)
            rows=[r for r in rows if (current-datetime.fromisoformat(r['observed_at'])).total_seconds()<=30*86400]
            selected=[];scope='insufficient_history'
            for fields,name in [(('task_class','model_id','effort'),'task_model_effort'),(('task_class','model_id'),'task_model'),(('task_class',),'task'),((),'global')]:
                requested={'task_class':task_class,'model_id':model_id,'effort':effort}
                candidates=[r for r in rows if all(r[k]==requested[k] for k in fields)]
                if len(candidates)>=5:selected=candidates;scope=name;break
            result={'prediction_id':ident,'task_class':task_class,'model_id':model_id,'effort':effort,
                    'runtime_version':runtime_version,'created_at':created,'sample_count':len(selected),
                    'available_completed_samples':len(rows),'scope':scope,'confidence':'unknown',
                    'duration_interval_ms':None,'duration_p50_ms':None,'duration_log_ewma_ms':None,
                    'total_tokens_p50':None,'total_tokens_p90':None,'token_sample_count':0,
                    'interval_kind':'empirical, uncalibrated; no coverage guarantee','drift_detected':False,
                    'source':'completed local observations; 200-row/30-day bounded window',
                    'reset_semantics':'runtime-version changes start an untrained estimate; observations retained'}
            if selected:
                values=[r['duration_ms'] for r in selected if r['duration_ms'] is not None]
                if len(values)>=5:
                    drift=len(values)>=10 and (statistics.median(values[:5])>2*max(1,statistics.median(values[5:])) or statistics.median(values[:5])<.5*statistics.median(values[5:]))
                    low,high=quantile(values,.1),quantile(values,.9)
                    ewma=math.log1p(values[-1])
                    for value in reversed(values[:-1]):ewma=.2*math.log1p(value)+.8*ewma
                    result.update(duration_interval_ms=[int(low*.5) if drift else low,int(high*2) if drift else high],
                        duration_p50_ms=statistics.median(values),duration_log_ewma_ms=round(math.expm1(ewma)),
                        confidence='low' if drift or len(values)<20 else 'medium',drift_detected=drift)
                tokens=[r['total_tokens'] for r in selected if r['total_tokens'] is not None]
                result['token_sample_count']=len(tokens)
                if len(tokens)>=5:result.update(total_tokens_p50=statistics.median(tokens),total_tokens_p90=quantile(tokens,.9))
            self.db.execute('INSERT INTO task_prediction VALUES(?,?,?,?,?,?,?)',(ident,task_class,model_id,effort,runtime_version,created,json.dumps(result,sort_keys=True)))
        return result
    def complete(self,prediction_id,*,status,duration_ms=None,total_tokens=None,success=None,at=None):
        if status not in {'completed','failed','timeout','cancelled','interrupted','superseded'}:raise ValueError('Invalid completion status')
        nonnegative(duration_ms);nonnegative(total_tokens)
        if success is not None and type(success) is not bool:raise ValueError('Quality label must be explicit boolean or unknown')
        if status=='completed' and duration_ms is None:raise ValueError('Completed duration required')
        if status in {'timeout','cancelled','interrupted','superseded'} and success is not None:raise ValueError('Censored quality remains unknown')
        observed=timestamp(at or datetime.now(timezone.utc).isoformat())
        payload_hash=identity([status,duration_ms,total_tokens,success,observed])
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            prediction=self.db.execute('SELECT * FROM task_prediction WHERE prediction_id=?',(prediction_id,)).fetchone()
            if not prediction:raise ValueError('Prediction must be recorded before completion')
            if observed<prediction['created_at']:raise ValueError('Completion predates prediction')
            existing=self.db.execute('SELECT payload_hash FROM task_observation WHERE prediction_id=?',(prediction_id,)).fetchone()
            if existing:
                if existing[0]!=payload_hash:raise ValueError('Conflicting completion')
                return
            forecast=json.loads(prediction['payload']);interval=forecast['duration_interval_ms']
            score={'censored':status in {'timeout','cancelled','interrupted','superseded'},'duration_interval_hit':None,'duration_absolute_error_ms':None}
            if status=='completed' and interval:
                score.update(duration_interval_hit=interval[0]<=duration_ms<=interval[1],duration_absolute_error_ms=abs(duration_ms-forecast['duration_p50_ms']))
            self.db.execute('INSERT INTO task_observation VALUES(?,?,?,?,?,?,?,?)',(prediction_id,observed,status,duration_ms,total_tokens,success,payload_hash,json.dumps(score)))
    def quality_history(self,*,at,runtime_version):
        current=datetime.fromisoformat(timestamp(at));result={}
        rows=self.db.execute('SELECT p.model_id,p.effort,o.* FROM task_observation o JOIN task_prediction p USING(prediction_id) WHERE p.runtime_version=? AND o.success IS NOT NULL ORDER BY o.observed_at DESC LIMIT 200',(runtime_version,)).fetchall()
        groups={}
        for row in rows:
            if not 0<=(current-datetime.fromisoformat(row['observed_at'])).total_seconds()<=30*86400:continue
            key=row['model_id']+'|'+row['effort'];stats=result.setdefault(key,{'sample_count':0,'successes':0,'observed_at':row['observed_at']})
            stats['sample_count']+=1;stats['successes']+=row['success']
            groups.setdefault(key,[]).append(row)
        for key,group in groups.items():
            durations=[r['duration_ms'] for r in group if r['status']=='completed' and r['duration_ms'] is not None]
            tokens=[r['total_tokens'] for r in group if r['total_tokens'] is not None]
            result[key]['median_duration_ms']=statistics.median(durations) if durations else None
            result[key]['median_total_tokens']=statistics.median(tokens) if tokens else None
        return result
