"""Local rule-based next-task advice. No runtime mutation or inference calls."""
from datetime import datetime, timezone
import math
from .ledger import timestamp

FEATURES={'files_touched_estimate','has_state_machine_change','has_protocol_change',
          'has_security_boundary_change','has_test_failure','requires_live_runtime','is_docs_only',
          'estimated_parallelizable_units'}


def recommend(catalog,features,policy,history=None,*,at=None):
    result={'selected':None,'alternatives':[],'confidence':'unknown','sample_count':0,
            'reason':'INSUFFICIENT_VERIFIED_INPUTS','additional_model_calls':0,'automatic_switch':False}
    try:
        if set(features)-FEATURES:raise ValueError('Unknown task features')
        for key,value in features.items():
            if key in {'files_touched_estimate','estimated_parallelizable_units'}:
                if type(value) is not int or value<0:raise ValueError('Invalid task size')
            elif type(value) is not bool:raise ValueError('Invalid task flag')
        current=datetime.fromisoformat(timestamp(at)) if at else datetime.now(timezone.utc)
        observed=datetime.fromisoformat(timestamp(catalog['observed_at']))
        age=(current-observed).total_seconds()
        if catalog.get('status')!='VERIFIED_CATALOG' or not 0<=age<=3600:
            return dict(result,reason='CATALOG_UNKNOWN_OR_STALE')
        risks={name for feature,name in [('has_state_machine_change','state'),('has_protocol_change','protocol'),
               ('has_security_boundary_change','security'),('has_test_failure','debug'),('requires_live_runtime','live')]
               if features.get(feature)}
        quality_floor=policy.get('quality_floor',.9)
        if type(quality_floor) not in (float,int) or not 0<quality_floor<=1:raise ValueError('Invalid quality floor')
        history=history or {};eligible=[]
        for model in catalog['models']:
            if model.get('available') is not True:continue
            for configured in policy.get('candidates',[]):
                if configured.get('model_id')!=model['id'] or configured.get('effort') not in model.get('reasoning_efforts',[]):continue
                if not risks<=set(configured.get('approved_for',[])):continue
                rank=configured.get('cost_rank');capability=configured.get('capability_rank')
                if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in (rank,capability)):continue
                key=model['id']+'|'+configured['effort'];stats=history.get(key,{})
                if stats:
                    try:
                        history_age=(current-datetime.fromisoformat(timestamp(stats['observed_at']))).total_seconds()
                        if not 0<=history_age<=30*86400:stats={}
                    except (KeyError,ValueError,TypeError):stats={}
                n=stats.get('sample_count',0);successes=stats.get('successes',0)
                if type(n) is not int or type(successes) is not int or not 0<=successes<=n:continue
                if n>=10 and (successes+1)/(n+2)<quality_floor:continue
                eligible.append({'model_id':model['id'],'effort':configured['effort'],'sample_count':n,
                    'smoothed_success':(successes+1)/(n+2) if n else None,
                    'cost_rank':rank,'capability_rank':capability,
                    'median_duration_ms':stats.get('median_duration_ms'),
                    'median_total_tokens':stats.get('median_total_tokens')})
        if not eligible:return dict(result,reason='NO_CANDIDATE_MEETS_EXPLICIT_SAFETY_AND_CAPABILITY_POLICY')
        # Cold-start safety work uses the operator's explicit capability ranking, never a model name.
        cold=bool(risks) and not any(row['sample_count']>=10 for row in eligible)
        eligible.sort(key=lambda row:(-row['capability_rank'],row['cost_rank'],row['model_id'],row['effort']) if cold else
                      (row['cost_rank'],-row['capability_rank'],row['model_id'],row['effort']))
        selected=eligible[0]
        return dict(result,selected=selected,alternatives=eligible[1:],sample_count=selected['sample_count'],
                    confidence='low' if selected['sample_count']<10 else 'medium',
                    reason='EXPLICIT_CAPABILITY_FLOOR_COLD_START' if cold else 'LOWEST_CONFIGURED_COST_RANK_MEETING_POLICY',
                    cost_source='operator-supplied ordinal policy; not measured monetary cost',catalog_age_seconds=age)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return dict(result,reason='INVALID_OR_INCOMPLETE_ADVICE_INPUT')
