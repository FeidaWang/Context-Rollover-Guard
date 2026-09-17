"""Monotonic milestone/interval projection with external acceptance evidence."""
from .events import instant, number


def union_ms(intervals):
    ordered = []
    for start, end in intervals:
        number(start, integer=True); number(end, integer=True)
        if start is None or end is None or end < start:
            raise ValueError('Invalid monotonic interval')
        ordered.append((start, end))
    total, last = 0, None
    for start, end in sorted(ordered):
        total += end - max(start, last if last is not None else start) if last is None or end > last else 0
        last = max(last if last is not None else end, end)
    return total


def summarize(events, *, approval_intervals=None, tool_intervals=None, acceptance=None):
    unique = {}
    for event in events:
        if set(event) != {'id', 'kind', 'process_id', 'monotonic_ms', 'at'}:
            raise ValueError('Only milestone metadata accepted')
        instant(event['at']); number(event['monotonic_ms'], integer=True)
        if event['kind'] not in {'submit', 'accepted', 'first_output', 'completed', 'cancelled', 'timeout', 'failed'}:
            raise ValueError('Unknown timing event')
        if event['id'] in unique and unique[event['id']] != event:
            raise ValueError('Conflicting milestone replay')
        unique[event['id']] = event
    rows = list(unique.values())
    starts = [r for r in rows if r['kind'] == 'submit']
    finishes = [r for r in rows if r['kind'] in {'completed','cancelled','timeout','failed'}]
    result = {'target': 'submit_to_model_finish', 'wall_ms': None, 'active_ms': None,
              'tool_union_ms': None, 'accepted': None, 'acceptance_ms': None,
              'status': 'INCOMPLETE', 'censored': True, 'quality_source': None}
    if len(starts) != 1 or len(finishes) != 1 or len({r['process_id'] for r in rows}) != 1:
        return result
    start, finish = starts[0]['monotonic_ms'], finishes[0]['monotonic_ms']
    if start is None or finish is None or finish < start:
        return result
    status = finishes[0]['kind']
    result.update(wall_ms=finish-start, status=status, censored=status in {'cancelled','timeout'})
    for intervals, key in ((approval_intervals, 'active_ms'), (tool_intervals, 'tool_union_ms')):
        if intervals is not None:
            if any(a < start or b > finish for a,b in intervals):
                raise ValueError('Segment outside task')
            duration = union_ms(intervals)
            result[key] = finish-start-duration if key == 'active_ms' else duration
    if acceptance is not None:
        if set(acceptance) != {'source','accepted','observed','monotonic_ms','process_id'}:
            raise ValueError('Explicit external acceptance evidence required')
        if (acceptance['source'] not in {'maintainer','executed_tests'} or acceptance['observed'] is not True
                or type(acceptance['accepted']) is not bool):
            raise ValueError('Unexecuted or self-rated quality is not evidence')
        result.update(accepted=acceptance['accepted'],quality_source=acceptance['source'])
        value = number(acceptance['monotonic_ms'],integer=True)
        if acceptance['process_id'] == starts[0]['process_id'] and value is not None and value >= finish:
            result['acceptance_ms'] = value-start
    return result
