"""Advice is a separate status surface; archived answer bytes are never modified."""
import math


def render_status(advice,estimate=None):
    try:
        selected=advice.get('selected') or {}
        def clean(value):return ' '.join(str(value).split())[:100]
        model=clean(selected.get('model_id') or 'unknown')
        effort=clean(selected.get('effort') or 'unknown')
        estimate=estimate or {}
        interval=estimate.get('duration_interval_ms')
        eta='unknown (insufficient or stale history)'
        if (isinstance(interval,list) and len(interval)==2 and
            all(type(value) in (int,float) and math.isfinite(value) and value>=0 for value in interval)
            and interval[0]<=interval[1]):
            eta=f'{interval[0]/60000:.1f}–{interval[1]/60000:.1f} min (empirical)'
        samples=estimate.get('sample_count',0)
        if type(samples) is not int or samples<0:samples=0
        confidence=clean(estimate.get('confidence','unknown'))
        return f'CRG next-task estimate — model: {model} | effort: {effort} | ETA: {eta} | confidence: {confidence} | samples: {samples}'
    except (ValueError,TypeError,AttributeError,OverflowError):
        return 'CRG next-task estimate — model: unknown | effort: unknown | ETA: unknown | confidence: unknown | samples: 0'


def presentation(raw_answer, advice, forecast, snapshot, *, at, protocol='markdown'):
    """Return separate presentation blocks; raw bytes never undergo decoding/editing."""
    import hashlib
    from datetime import datetime
    from .events import instant
    from .features import matches
    if not isinstance(raw_answer,bytes):raise ValueError('Exact raw answer bytes required')
    valid=forecast is not None and matches(forecast,snapshot)
    age=(datetime.fromisoformat(instant(at))-datetime.fromisoformat(forecast['as_of'])).total_seconds() if valid else None
    if age is not None and not 0<=age<=3600:valid=False
    selected=advice.get('selected') if valid else None
    if valid and (not selected or selected.get('model_id')!=snapshot['policy']['model_id'] or selected.get('effort')!=snapshot['policy']['effort']):
        valid=False;selected=None
    def clean(value):return ' '.join(str(value).split())[:100]
    interval=forecast.get('interval') if valid and forecast.get('target')=='wall_ms' else None
    eta='未校准'
    if (isinstance(interval,list) and len(interval)==2 and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in interval) and interval[0]<=interval[1]):
        eta=f'{interval[0]/60000:.1f}–{interval[1]/60000:.1f} 分钟（经验区间）'
    text=(f"下一任务建议｜模型 {clean((selected or {}).get('model_id','未验证'))}｜"
          f"强度 {clean((selected or {}).get('effort','未验证'))}｜单 agent｜预计耗时：{eta}｜"
          f"数据年龄：{age if valid else '未知'} 秒｜依据：{clean(forecast.get('status')) if valid else 'NEXT_TASK_UNKNOWN_OR_CHANGED'}")
    return {'raw_answer':raw_answer,'raw_sha256':hashlib.sha256(raw_answer).hexdigest(),
            'status_line':text,'placement':'separate_status_surface' if protocol!='owned_blocks' else 'before_declared_conclusion',
            'additional_model_calls':0,'status_utf8_bytes':len(text.encode()),'tokenizer_count':None}
