"""Local-only account fallback and explicit calendar/provider reconciliation."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .events import instant, number


def unavailable():
    return {'status': 'UNSUPPORTED', 'reason': 'NO_VERIFIED_ACCOUNT_ACTIVITY_CONTRACT',
            'daily_buckets': None, 'total_tokens': None, 'model_calls': 0}


def interval(mode, *, at, timezone_name='UTC', provider_start=None, provider_end=None):
    current = datetime.fromisoformat(instant(at))
    if mode == 'calendar_week':
        local = current.astimezone(ZoneInfo(timezone_name))
        start = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    elif mode == 'rolling_168h':
        start, end = current - timedelta(hours=168), current
    elif mode == 'provider_window':
        start, end = datetime.fromisoformat(instant(provider_start)), datetime.fromisoformat(instant(provider_end))
    else:
        raise ValueError('Unknown query interval')
    if start >= end:
        raise ValueError('Invalid interval')
    return instant(start.isoformat()), instant(end.isoformat())


def reconcile(local, buckets, *, start, end, provider_timezone=None):
    """Already authorized numeric buckets only; never fetch a private endpoint."""
    start, end = instant(start), instant(end)
    if start >= end:
        raise ValueError('Invalid interval')
    result = {'local': local, 'account_total_tokens': None, 'account_bounds_tokens': None,
              'reconciliation': 'UNAVAILABLE', 'provider_timezone': provider_timezone,
              'coverage': 'local observed events; other devices/subagents may be absent',
              'additive': False, 'time_basis': 'provider_day', 'bucket_count': None}
    if buckets is None:
        return result
    if not isinstance(buckets, list):
        raise ValueError('Nullable bucket list required')
    result['bucket_count'] = len(buckets)
    if provider_timezone is None:
        return dict(result, reconciliation='UNKNOWN_BUCKET_TIMEZONE')
    zone = ZoneInfo(provider_timezone)
    low, high, seen = 0, 0, set()
    for bucket in buckets:
        if set(bucket) != {'date', 'total_tokens'}:
            raise ValueError('Only provider date and numeric total accepted')
        day = datetime.strptime(bucket['date'], '%Y-%m-%d').replace(tzinfo=zone)
        if bucket['date'] in seen:
            raise ValueError('Duplicate daily bucket')
        seen.add(bucket['date'])
        a, b = instant(day.isoformat()), instant((day + timedelta(days=1)).isoformat())
        total = number(bucket['total_tokens'], integer=True)
        if a < end and b > start:
            if total is None:
                return dict(result, reconciliation='UNKNOWN_BUCKET_VALUE')
            high += total
            if a >= start and b <= end:
                low += total
    return dict(result, account_bounds_tokens=[low, high],
                account_total_tokens=low if low == high else None,
                reconciliation='RETURNED_BUCKETS_ONLY' if low == high else 'BOUNDARY_BUCKET_UNCERTAINTY')
