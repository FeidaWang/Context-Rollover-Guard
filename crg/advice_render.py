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
