"""Local rule-based next-task advice. No runtime mutation or inference calls."""
from datetime import datetime, timezone
import math
from .ledger import timestamp

FEATURES={'files_touched_estimate','has_state_machine_change','has_protocol_change',
          'has_security_boundary_change','has_test_failure','requires_live_runtime','is_docs_only',
          'estimated_parallelizable_units'}


def recommend(catalog,features,policy,history=None,*,at=None):
    result={'selected':None,'alternatives':[],'confidence':'unknown','sample_count':0,
            'reason':'INSUFFICIENT_VERIFIED_INPUTS','additional_model_calls':0,'automatic_switch':False,
            'actionable':False,'execution_mode':'single_agent',
            'execution_contract':'UNVERIFIED_PREVIEW_REQUIRES_RESOLUTION'}
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
            efforts=model.get('reasoning_efforts', [])
            if (not isinstance(model.get('id'), str) or not model['id']
                    or not isinstance(efforts, (list, tuple))
                    or not all(isinstance(value, str) and value for value in efforts)):continue
            for configured in policy.get('candidates',[]):
                if set(configured)-{'model_id','effort','cost_rank','capability_rank','approved_for'}:
                    continue  # Advice never authorizes tools, agents, network or permission changes.
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


def recommend_verified(catalog, features, policy, requirements, history=None, *, at=None):
    """Stricter opt-in advice contract. Missing capability evidence fails closed.

    A host must still resolve the selected execution against the current runtime.
    Observational histories do not establish causal model superiority.
    """
    required={'modalities','tools','permission_profile','context_tokens','risk'}
    if (not isinstance(requirements,dict) or set(requirements)!=required
            or not isinstance(requirements['modalities'],list) or not isinstance(requirements['tools'],list)
            or not all(isinstance(v,str) for v in requirements['modalities']+requirements['tools'])
            or type(requirements['context_tokens']) is not int or requirements['context_tokens']<0
            or requirements['risk'] not in {'low','medium','high'}):
        return {'selected':None,'reason':'UNKNOWN_REQUIREMENTS','additional_model_calls':0,'automatic_switch':False}
    filtered=[]
    for model in catalog.get('models',[]):
        capability=model.get('capabilities',{})
        if (capability.get('verified') is not True
                or not set(requirements['modalities'])<=set(capability.get('modalities',[]))
                or not set(requirements['tools'])<=set(capability.get('tools',[]))
                or requirements['permission_profile'] not in capability.get('permission_profiles',[])
                or type(capability.get('context_tokens')) is not int
                or capability['context_tokens']<requirements['context_tokens']
                or requirements['risk'] not in capability.get('approved_risks',[])):
            continue
        filtered.append(model)
    result=recommend(dict(catalog,models=filtered),features,policy,history,at=at)
    result.update(evidence='observational or operator heuristic; not a causal ranking',
                  required_capabilities=requirements)
    return result


def accepted_workflow_cost(workflows):
    """All attempts including failures/repairs; distinct units, no scalar score."""
    from .events import number
    seen=set();rows=[]
    for row in workflows:
        if row.get('quality_source') not in {'maintainer','executed_tests'} or type(row.get('accepted')) is not bool:
            return {'status':'UNKNOWN_QUALITY','cost_per_accepted_task':None}
        if not isinstance(row.get('task_id'),str) or row['task_id'] in seen:
            raise ValueError('One complete workflow per independent task required')
        seen.add(row['task_id']);rows.append(row)
    accepted=sum(row['accepted'] for row in rows)
    costs={}
    for unit in ('tokens','wall_ms','quota_percent','money'):
        values=[number(row.get(unit)) for row in rows]
        costs[unit]=sum(values)/accepted if accepted and all(v is not None for v in values) else None
    return {'status':'OBSERVATIONAL','accepted_tasks':accepted,'attempted_tasks':len(rows),
            'cost_per_accepted_task':costs,'causal_ranking':False}
