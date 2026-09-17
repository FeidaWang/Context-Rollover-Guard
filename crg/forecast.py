"""Bounded, revision-aware prequential baseline forecasts on local numeric data."""
import json
from statistics import median
from .events import instant, number
from .ledger import connect, identity
from .calibration_online import score, metrics, drift
from .features import validate_snapshot

TARGETS={'wall_ms','active_ms','total_tokens'}


def quantile(values,q):
    ordered=sorted(values)
    return ordered[int((len(ordered)-1)*q)]


class Forecasts:
    def __init__(self,path):
        self.db=connect(path)
        with self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS forecast_v1(id TEXT PRIMARY KEY, cohort TEXT NOT NULL, at TEXT NOT NULL,payload TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS outcome_v1(id TEXT NOT NULL,revision INTEGER NOT NULL,at TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(id,revision))')
            self.db.execute('CREATE INDEX IF NOT EXISTS forecast_cohort ON forecast_v1(cohort,at)')
            self.db.execute('CREATE INDEX IF NOT EXISTS outcome_time ON outcome_v1(at)')

    def close(self):self.db.close()

    def _history(self,cohort,at):
        # Bounded independent tasks. Corrections only participate after arrival.
        rows=self.db.execute('''SELECT f.id,f.payload AS prediction,o.payload AS outcome
            FROM forecast_v1 f JOIN outcome_v1 o ON o.id=f.id
            WHERE f.cohort=? AND o.at<? AND o.revision=(
                SELECT max(x.revision) FROM outcome_v1 x WHERE x.id=f.id AND x.at<?)
            ORDER BY o.at DESC,f.id LIMIT 200''',(cohort,at,at)).fetchall()
        selected=[];seen=set()
        for row in rows:
            prediction=json.loads(row['prediction'])
            if prediction['task_id'] in seen:continue
            seen.add(prediction['task_id']);selected.append((prediction,json.loads(row['outcome'])))
        return list(reversed(selected))

    def predict(self,snapshot,*,target='wall_ms'):
        if snapshot.get('status')!='CONFIRMED':
            return {'status':'NEXT_TASK_UNKNOWN','interval':None}
        validate_snapshot(snapshot)
        if target not in TARGETS:
            raise ValueError('Separate known forecast target required')
        at=instant(snapshot['as_of'])
        cohort=identity([snapshot['kind'],snapshot['risk'],snapshot['policy'],snapshot['feature_version'],target])
        ident=identity([snapshot['task_id'],snapshot['intent_hash'],snapshot['policy'],target])
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            old=self.db.execute('SELECT payload FROM forecast_v1 WHERE id=?',(ident,)).fetchone()
            if old:return json.loads(old[0])
            history=self._history(cohort,at)
            completed=[o['value'] for _,o in history if o['status']=='completed' and o['value'] is not None and not o['intervened']]
            scores=[o['score'] for _,o in history if o['status']=='completed' and not o['intervened']]
            trend=drift(scores)
            current_features=[snapshot.get(k) for k in ('file_count','acceptance_count','input_bytes','retry_count')]
            outside=False
            if len(history)>=10:
                for i,key in enumerate(('file_count','acceptance_count','input_bytes','retry_count')):
                    values=[p['features'].get(key) for p,_ in history if p['features'].get(key) is not None]
                    if values and current_features[i] is not None and current_features[i]>max(1,max(values))*2:
                        outside=True
            enough=len(completed)>=5
            # Always use declared rolling-median baseline until an independent
            # chronological experiment supports a more complex predictor.
            result={'schema_version':1,'predictor_version':'rolling-median-v1','id':ident,
                'task_id':snapshot['task_id'],'intent_hash':snapshot['intent_hash'],
                'feature_version':snapshot['feature_version'],'policy':snapshot['policy'],
                'as_of':at,'cohort':cohort,'target':target,'features':snapshot,
                'status':'EMPIRICAL_BASELINE' if enough else 'INSUFFICIENT_CALIBRATION',
                'median':median(completed) if enough else None,
                'interval':[quantile(completed,.1),quantile(completed,.9)] if enough else None,
                'interval_kind':'empirical nominal 80%; no per-task guarantee',
                'sample_count':len(completed),'effective_sample_size':len(completed),
                'censoring_rate':sum(o['status'] in {'cancelled','timeout','interrupted'} for _,o in history)/len(history) if history else None,
                'metrics':metrics(scores),'drift':trend,'model_calls':0,'borrowed_cohort':False}
            if outside or trend['fallback']:
                result.update(status='FEATURE_RANGE_FALLBACK' if outside else 'DRIFT_FALLBACK',interval=None,median=None)
                # Re-entry tests rolling data distribution, not self-produced
                # UNKNOWN scores, so a stable recent regime can recover.
                recent=completed[-10:]
                if not outside and len(recent)==10 and max(recent)<=max(1,min(recent))*1.5:
                    result.update(status='RECENT_BASELINE_FALLBACK',median=median(recent),interval=[min(recent),max(recent)])
            self.db.execute('INSERT INTO forecast_v1 VALUES(?,?,?,?)',(ident,cohort,at,json.dumps(result,sort_keys=True)))
        return result

    def complete(self,ident,*,revision=0,at,status,value=None,intervened=False):
        if type(revision) is not int or revision<0 or type(intervened) is not bool:
            raise ValueError('Invalid outcome revision')
        if status not in {'completed','failed','cancelled','timeout','interrupted'}:
            raise ValueError('Explicit outcome status required')
        number(value,integer=True)
        if status=='completed' and value is None:
            raise ValueError('Completed target must be observed')
        at=instant(at)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row=self.db.execute('SELECT payload FROM forecast_v1 WHERE id=?',(ident,)).fetchone()
            if row is None:raise ValueError('Persist prediction before revealing outcome')
            prediction=json.loads(row[0])
            if at<prediction['as_of']:raise ValueError('Outcome predates prediction')
            payload={'revision':revision,'at':at,'status':status,'value':value,'intervened':intervened,
                     'score':score(prediction,value) if status=='completed' and not intervened else None}
            encoded=json.dumps(payload,sort_keys=True)
            old=self.db.execute('SELECT payload FROM outcome_v1 WHERE id=? AND revision=?',(ident,revision)).fetchone()
            if old:
                if old[0]!=encoded:raise ValueError('Conflicting outcome revision')
                return
            previous=self.db.execute('SELECT revision,at FROM outcome_v1 WHERE id=? ORDER BY revision DESC LIMIT 1',(ident,)).fetchone()
            if previous and (revision<=previous['revision'] or at<previous['at']):
                raise ValueError('Revision and arrival time must increase')
            self.db.execute('INSERT INTO outcome_v1 VALUES(?,?,?,?)',(ident,revision,at,encoded))
