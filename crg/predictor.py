"""Transparent, uncalibrated risk estimate. Never arms the production state."""
from dataclasses import asdict, dataclass
import math
from statistics import median
from .config import Predictor


def token_count(value, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError("Invalid token count")
    return value


@dataclass(frozen=True)
class Limit:
    tokens: int | None
    source: str
    scope: str
    precise: bool = False


def resolve_limit(window: int | None, configured: int | None = None, *,
                  scope: str = "unknown", prefix_tokens: int | None = None,
                  config: Predictor | None = None) -> Limit:
    c = config or Predictor()
    if window is not None: token_count(window, positive=True)
    if configured is not None: token_count(configured, positive=True)
    if prefix_tokens is not None: token_count(prefix_tokens)
    if scope not in {"total", "body_after_prefix", "unknown"}:
        raise ValueError("Unsupported compact limit scope")
    if window is None:
        return Limit(None, "window_unobservable", scope)
    derived = math.floor(window * c.derived_limit_percent)
    if scope == "total":
        return Limit(min(configured, derived) if configured is not None else derived,
                     "configured_capped_by_derived" if configured is not None else "derived_window_fraction", scope)
    if scope == "body_after_prefix" and prefix_tokens is not None and configured is not None:
        return Limit(min(configured + prefix_tokens, derived), "body_limit_plus_observed_prefix_capped", scope)
    conservative = math.floor(window * c.conservative_limit_percent)
    return Limit(min(configured, conservative) if configured is not None else conservative,
                 "conservative_estimate", scope)


def percentile75(values):
    values = sorted(values)
    if not values: return 0
    pos = (len(values)-1) * .75
    lo, hi = math.floor(pos), math.ceil(pos)
    return values[lo] + (values[hi]-values[lo]) * (pos-lo)


def predict(active: int | None, window: int | None, deltas: list[int], limit: Limit,
            config: Predictor | None = None) -> dict:
    c = config or Predictor()
    if active is not None: token_count(active)
    if window is not None: token_count(window, positive=True)
    if limit.tokens is not None: token_count(limit.tokens, positive=True)
    if not isinstance(deltas, list): raise ValueError("Invalid history")
    for delta in deltas: token_count(delta)
    if active is None or window is None or limit.tokens is None:
        return {"decision": "UNKNOWN", "reason_code": "INSUFFICIENT_TELEMETRY",
                "active_tokens": active, "limit_tokens": limit.tokens, "risk_score": None,
                "threshold_source": limit.source, "calibrated_probability": False}
    history = [d for d in deltas if d > 0][-c.window_size:]
    growth = math.ceil(max(percentile75(history), history[-1] if history else 0,
                           median(history)*1.25 if history else 0, c.min_growth_tokens))
    buffer = math.ceil(max(c.safety_buffer_tokens, window*c.safety_buffer_percent))
    headroom = limit.tokens-active
    peak = active+growth+buffer
    over = peak >= limit.tokens
    hard = headroom <= c.hard_arm_remaining_tokens
    return {"decision": "ARM" if over or hard else "SAFE", "active_tokens": active,
            "limit_tokens": limit.tokens, "predicted_growth": growth,
            "safety_buffer": buffer, "headroom": headroom, "predicted_peak": peak,
            "risk_score": min(1.0, (growth+buffer)/max(1,headroom)),
            "reason_code": "PREDICTED_NEXT_TURN_OVER_LIMIT" if over else
                "HARD_HEADROOM" if hard else "WITHIN_ESTIMATED_LIMIT",
            "threshold_source": limit.source, "limit": asdict(limit), "calibrated_probability": False}
