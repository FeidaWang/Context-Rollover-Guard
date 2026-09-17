"""Pure prequential scoring. No configuration or recovery writes."""
import math
from statistics import mean


def pinball(actual, predicted, q):
    residual=actual-predicted
    return max(q*residual,(q-1)*residual)


def update_bias(bias, base_log, actual, alpha=.1):
    if not 0 < alpha <= 1 or actual < 0:
        raise ValueError('Invalid calibration update')
    return (1-alpha)*bias + alpha*(math.log1p(actual)-base_log)


def score(prediction, actual):
    if actual is None or prediction['interval'] is None:
        return None
    lo,hi=prediction['interval'];center=prediction['median']
    return {'error':actual-center,'absolute_error':abs(actual-center),
            'pinball_10':pinball(actual,lo,.1),'pinball_90':pinball(actual,hi,.9),
            'covered':lo<=actual<=hi,'width':hi-lo}


def metrics(scores):
    known=[s for s in scores if s is not None]
    return {'sample_count':len(known),'effective_sample_size':len(known),
            'bias':mean(s['error'] for s in known) if known else None,
            'mae':mean(s['absolute_error'] for s in known) if known else None,
            'pinball_loss':mean((s['pinball_10']+s['pinball_90'])/2 for s in known) if known else None,
            'coverage':mean(s['covered'] for s in known) if known else None,
            'interval_width':mean(s['width'] for s in known) if known else None,
            'independence':'one latest outcome per task; project independence not assumed'}


def drift(scores):
    measured=metrics([s for s in scores if s is not None][-20:])
    active=(measured['sample_count']>=10 and
            (measured['coverage']<.5 or abs(measured['bias'])>max(1,measured['interval_width'])))
    return dict(measured, fallback=active, reason='UNDERCOVERAGE_OR_BIAS' if active else 'NO_PERSISTENT_DRIFT')
