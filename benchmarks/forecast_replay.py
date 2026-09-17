"""Chronological synthetic baseline comparison; no fitted-success claims."""
import json
from pathlib import Path
from statistics import median
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crg.calibration_online import score,metrics
from crg.forecast import quantile


def run():
    # Includes tiny values, abrupt/gradual drift, return, and heavy tails.
    sequences={'constant':[100]*60,'tiny':[0,1,0,2]*20,
               'shift':[100]*25+[1000]*25+[100]*25,
               'gradual':list(range(10,800,10)),
               'heavy_tail':[100]*20+[10000]+[100]*20+[100000]+[100]*20}
    results=[]
    for project,values in sequences.items():
        scores={name:[] for name in ('constant','last_value','rolling_median')}
        for i,value in enumerate(values):
            past=values[max(0,i-20):i]
            if len(past)<5:continue
            for name,center in [('constant',100),('last_value',past[-1]),('rolling_median',median(past))]:
                interval=[quantile(past,.1),quantile(past,.9)] if name=='rolling_median' else [center,center]
                scores[name].append(score({'median':center,'interval':interval},value))
        results.append({'project':project,'tasks':len(values),'baselines':{name:metrics(rows) for name,rows in scores.items()}})
    return {'schema_version':1,'evidence':'synthetic','selection':'rolling_median baseline; no complex estimator enabled',
            'split':'strict prefix training, next task evaluation; projects reported separately',
            'live_samples':0,'causal_model_comparison':False,'projects':results}

if __name__=='__main__':print(json.dumps(run(),indent=2))
