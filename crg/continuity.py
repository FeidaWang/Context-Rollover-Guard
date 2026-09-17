"""Continuation policy is independent of durable transaction state."""
from enum import Enum


class Policy(str, Enum):
    OBSERVE = 'OBSERVE'
    WARN = 'WARN'
    HANDOFF_READY = 'HANDOFF_READY'
    MIGRATE_EXPLICIT = 'MIGRATE_EXPLICIT'
    RECOVERY_REQUIRED = 'RECOVERY_REQUIRED'


def decide(*, ambiguous=False, explicit_fresh=False, handoff_ready=False,
           native_healthy=False, high_pressure=False):
    if ambiguous: return Policy.RECOVERY_REQUIRED
    if explicit_fresh: return Policy.MIGRATE_EXPLICIT
    if handoff_ready: return Policy.HANDOFF_READY
    if native_healthy: return Policy.OBSERVE
    return Policy.WARN if high_pressure else Policy.OBSERVE


def quiet_point(client, thread_id):
    """Ask a runtime adapter for fresh, complete activity, never infer from silence."""
    reader = getattr(client, 'read_activity', None)
    if not callable(reader): return False
    try:
        snapshot = reader(thread_id)
        if snapshot.get('thread_id') != thread_id or snapshot.get('complete') is not True:
            return False
        if snapshot.get('turn_state') not in {'completed', 'failed', 'cancelled', 'idle'}:
            return False
        for key in ('tools', 'children'):
            items = snapshot.get(key)
            if not isinstance(items, list): return False
            if any(not isinstance(item, dict) or item.get('state') not in
                   {'completed', 'failed', 'cancelled', 'detached'} for item in items): return False
        return True
    except (OSError, ValueError, RuntimeError, TypeError, AttributeError, KeyError):
        return False
