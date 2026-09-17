"""Conditional comparable-task capacity, never provider token balance."""
import math
from .events import instant, number
from .forecast import quantile


def capacity(buckets,samples,*,policy_hash,at,reserve_percent=5,coverage_complete=False):
    at=instant(at);number(reserve_percent)
    if reserve_percent is None or reserve_percent>100:raise ValueError('Invalid reserve')
    result={'status':'UNKNOWN','comparable_tasks':None,'limiting_bucket':None,'buckets':[],
            'tokens_remaining':None,'policy_hash':policy_hash,'valid_before':None,
            'reason':'INCOMPLETE_QUOTA_COVERAGE','guarantee':False}
    if not coverage_complete or not buckets:return result
    limits=[];ids=set()
    for bucket in buckets:
        key=(bucket.get('bucket_id'),bucket.get('epoch_id'))
        if key in ids:raise ValueError('Duplicate quota bucket')
        ids.add(key)
        remaining=number(bucket.get('remaining_percent'))
        resolution=number(bucket.get('resolution_percent'))
        reset=bucket.get('reset_at')
        if (bucket.get('status')!='OBSERVED' or not all(isinstance(v,str) and v for v in key)
                or remaining is None or remaining>100 or resolution is None or resolution<=0
                or reset is None or instant(reset)<=at):
            return dict(result,reason='STALE_OR_UNKNOWN_BUCKET')
        selected=[];seen=set()
        for sample in samples:
            if (sample.get('policy_hash')!=policy_hash or sample.get('bucket_id')!=key[0]
                or sample.get('start_epoch')!=key[1] or sample.get('end_epoch')!=key[1]
                or sample.get('complete') is not True or sample.get('external_activity') is not False):continue
            task=sample.get('task_id')
            if not isinstance(task,str) or task in seen:continue
            if instant(sample['completed_at'])>=at:continue
            value=number(sample.get('used_percent'))
            if value is None:continue
            seen.add(task);selected.append(value)
        if len(selected)<5:return dict(result,reason='INSUFFICIENT_ATTRIBUTABLE_TASKS')
        cost=quantile(selected,.9)
        if cost<resolution:return dict(result,reason='BELOW_PERCENTAGE_RESOLUTION')
        estimate=math.floor(max(0,remaining-reserve_percent)/(cost+resolution))
        result['buckets'].append({'bucket_id':key[0],'epoch_id':key[1],'official_remaining_percent':remaining,
                                  'sample_count':len(selected),'task_consumption_p90_percent':cost,
                                  'resolution_percent':resolution,'comparable_tasks':estimate})
        limits.append((estimate,key[0],instant(reset)))
    limiting=min(limits)
    return dict(result,status='CONDITIONAL_ESTIMATE',comparable_tasks=limiting[0],limiting_bucket=limiting[1],
                valid_before=min(x[2] for x in limits),reason='FIXED_POLICY_BEFORE_EARLIEST_RESET')
