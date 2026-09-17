"""Stable content-free side-panel status and event-driven read coalescing."""
from copy import deepcopy
import threading
import time
from .account import unavailable


class RefreshCache:
    def __init__(self, ttl=60, clock=time.monotonic):
        if type(ttl) not in (int,float) or not 0 <= ttl <= 3600:
            raise ValueError('Invalid refresh TTL')
        self.ttl, self.clock = ttl, clock
        self.values = {}; self.lock = threading.Lock()

    def get(self, key, read, *, refresh=False, event_id=None):
        with self.lock:
            current = self.clock(); cached = self.values.get(key)
            same_event = cached and event_id is not None and cached['event_id'] == event_id
            if not same_event and (cached is None or refresh or current-cached['at'] >= self.ttl):
                value = read()
                cached = {'value':deepcopy(value),'at':self.clock(),'event_id':event_id}
                self.values[key] = cached
                # Bound memory; eviction never triggers a background read.
                if len(self.values) > 128:
                    del self.values[next(iter(self.values))]
            return {'value':deepcopy(cached['value']), 'age_seconds':max(0,self.clock()-cached['at'])}

    def invalidate(self,key):
        with self.lock: self.values.pop(key,None)


def status(local, *, context=None, quota=None, timing=None):
    return {'schema_version':1, 'context':context or {'status':'UNKNOWN','active_context_tokens':None},
            'usage':{'local':local,'account':unavailable()},
            'quota':quota or {'status':'UNKNOWN','remaining_percent':None,'tokens_remaining':None},
            'timing':timing or {'status':'UNKNOWN','wall_ms':None},
            'additional_model_calls':0, 'background_polling':False}


def human(value):
    local = value['usage']['local']; quota = value['quota']; context = value['context']
    def show(v): return 'UNKNOWN' if v is None else str(v)
    return ('CRG local status\n'
            f"Context gauge: {show(context.get('active_context_tokens'))}\n"
            f"Local observed tokens: {show(local.get('known_total_tokens'))} ({local.get('coverage','unknown')})\n"
            f"Account activity: {value['usage']['account']['status']}\n"
            f"Quota remaining percent: {show(quota.get('remaining_percent'))} ({quota.get('status','UNKNOWN')})\n"
            'Usage, context and quota are separate quantities. No background inference.')
