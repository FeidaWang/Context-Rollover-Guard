"""Confirmed task projections. No classifier, embeddings or retained prose."""
from .events import instant, number
from .ledger import identity

POLICY = {'model_id','effort','runtime_version','service_tier','execution_mode','tool_family'}


def features(intent, policy, *, at):
    if intent is None:
        return {'status':'NEXT_TASK_UNKNOWN','forecast':None}
    if not isinstance(intent,dict) or set(intent)-{'task_id','confirmed','kind','risk','files','acceptance','description','input_bytes','headroom_tokens','retry_count'}:
        raise ValueError('Explicit task contract required')
    if intent.get('confirmed') is not True or not isinstance(intent.get('task_id'),str) or not intent['task_id']:
        return {'status':'NEXT_TASK_UNKNOWN','forecast':None}
    if intent.get('kind') not in {'docs','code','test','protocol','security','analysis'} or intent.get('risk') not in {'low','medium','high'}:
        raise ValueError('Explicit kind and risk required')
    if set(policy) != POLICY or any(not isinstance(v,str) or not v for v in policy.values()):
        raise ValueError('Complete execution policy required')
    if policy['execution_mode'] != 'single_agent':
        raise ValueError('Multi-agent forecasting lacks verified budget/aggregation contract')
    for key in ('files','acceptance'):
        if not isinstance(intent.get(key),list) or not all(isinstance(v,str) for v in intent[key]):
            raise ValueError('Explicit target and acceptance lists required')
    for key in ('input_bytes','headroom_tokens','retry_count'):
        number(intent.get(key),integer=True)
    if not isinstance(intent.get('description',''),str):
        raise ValueError('Description must be inert text')
    return {'status':'CONFIRMED','task_id':identity(intent['task_id']), 'intent_hash':identity(intent),
            'feature_version':1,'as_of':instant(at),'policy':dict(policy),
            'kind':intent['kind'],'risk':intent['risk'], 'file_count':len(intent['files']),
            'acceptance_count':len(intent['acceptance']), 'input_bytes':intent.get('input_bytes'),
            'headroom_tokens':intent.get('headroom_tokens'),'retry_count':intent.get('retry_count'),
            'size_semantics':'bytes are a rough feature, not billed tokens'}


def matches(prediction,snapshot):
    return (snapshot.get('status')=='CONFIRMED' and prediction.get('intent_hash')==snapshot.get('intent_hash')
            and prediction.get('policy')==snapshot.get('policy')
            and prediction.get('feature_version')==snapshot.get('feature_version'))


def validate_snapshot(snapshot):
    import re
    fields={'status','task_id','intent_hash','feature_version','as_of','policy','kind','risk',
            'file_count','acceptance_count','input_bytes','headroom_tokens','retry_count','size_semantics'}
    if not isinstance(snapshot,dict) or set(snapshot)!=fields or snapshot['status']!='CONFIRMED':
        raise ValueError('Only a confirmed projected feature snapshot is accepted')
    if type(snapshot['feature_version']) is not int or snapshot['feature_version']!=1:
        raise ValueError('Unsupported feature contract')
    for key in ('task_id','intent_hash'):
        if not isinstance(snapshot[key],str) or not re.fullmatch('[0-9a-f]{64}',snapshot[key]):
            raise ValueError('Projected identity hash required')
    for key in ('file_count','acceptance_count','input_bytes','headroom_tokens','retry_count'):
        number(snapshot[key],integer=True)
    if snapshot['kind'] not in {'docs','code','test','protocol','security','analysis'} or snapshot['risk'] not in {'low','medium','high'}:
        raise ValueError('Invalid task cohort')
    policy=snapshot['policy']
    if set(policy)!=POLICY or any(not isinstance(v,str) or not v or len(v)>256 for v in policy.values()) or policy['execution_mode']!='single_agent':
        raise ValueError('Invalid execution policy')
    if snapshot['size_semantics']!='bytes are a rough feature, not billed tokens':
        raise ValueError('Unknown size semantics')
    instant(snapshot['as_of'])
