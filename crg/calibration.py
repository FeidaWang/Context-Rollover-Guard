"""Per-model empirical metrics. Suggestions never silently alter predictor configuration."""

from statistics import median

def summarize(samples,*,minimum_samples=20):
    if type(minimum_samples)is not int or minimum_samples<20:raise ValueError('Calibration requires at least 20 real boundaries')
    groups={};seen={}
    for sample in samples:
        if not isinstance(sample,dict) or not sample.get('verified_real'):continue
        model=sample.get('model');active=sample.get('active_context_tokens');limit=sample.get('observed_compact_limit')
        if not isinstance(model,str) or not model:raise ValueError('Model identity required')
        if type(active)is not int or active<0:raise ValueError('Active context required; cumulative counters are not accepted')
        if limit is not None and (type(limit)is not int or limit<=0):raise ValueError('Invalid observed limit')
        identity=(sample.get('runtime_version'),sample.get('limit_scope'))
        if not all(isinstance(x,str) and x for x in identity):raise ValueError('Runtime and scope required')
        event=sample.get('event_id')
        if not isinstance(event,str) or not event:raise ValueError('Unique boundary event id required')
        key=(model,*identity,event)
        if key in seen:
            if seen[key]!=sample:raise ValueError('Conflicting calibration sample')
            continue
        seen[key]=sample
        groups.setdefault((model,*identity),[]).append(sample)
    result=[]
    for (model,version,scope),rows in sorted(groups.items()):
        boundaries=[r for r in rows if r.get('automatic_precompact') is True]
        limits=[r['observed_compact_limit'] for r in boundaries if scope in {'total','body_after_prefix'} and r.get('observed_compact_limit') is not None]
        evaluated=[r for r in rows if type(r.get('armed_before')) is bool and
                   (r.get('automatic_precompact') is True or r.get('outcome_observed') is True and type(r.get('automatic_precompact')) is bool)]
        tp=sum(r['armed_before'] and r['automatic_precompact'] for r in evaluated)
        fn=sum(not r['armed_before'] and r['automatic_precompact'] for r in evaluated)
        fp=sum(r['armed_before'] and not r['automatic_precompact'] for r in evaluated)
        tn=sum(not r['armed_before'] and not r['automatic_precompact'] for r in evaluated)
        ratio=lambda a,b:a/b if b else None
        leads={}
        for field in ('warning_lead_tokens','warning_lead_turns'):
            values=[r[field] for r in evaluated if r['armed_before'] and r['automatic_precompact'] and r.get(field) is not None]
            if any(type(v)is not int or v<0 for v in values):raise ValueError('Invalid observed warning lead')
            leads['median_'+field]=median(values) if values else None
        missed=fn
        result.append({'model':model,'runtime_version':version,'limit_scope':scope,'samples':len(rows),
            'automatic_precompact_samples':len(boundaries),'prediction_misses':missed,
            'miss_rate':ratio(fn,tp+fn),'precision':ratio(tp,tp+fp),'recall':ratio(tp,tp+fn),
            'false_positive_rate':ratio(fp,fp+tn),'false_negative_rate':ratio(fn,tp+fn),
            'evaluated_outcomes':len(evaluated),**leads,
            'status':'SUGGESTION_ONLY' if len(limits)>=minimum_samples else 'INSUFFICIENT_REAL_BOUNDARIES',
            'suggested_conservative_limit':sorted(limits)[max(0,int(len(limits)*.1)-1)] if len(limits)>=minimum_samples else None,
            'configuration_changed':False})
    return result
