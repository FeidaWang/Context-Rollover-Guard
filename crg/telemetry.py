"""Ordered App Server event ingestion, explicitly invoked in MODE_A only.

No socket interception, user prompt processing, hook output or thread mutation.
Only final per-turn usage contributes to growth; per-request usage updates within
one turn are never mislabeled as multiple turns. State is the authoritative log.
"""
from dataclasses import replace
from .domain import Mode, State
from .logging import append_event
from .predictor import token_count, resolve_limit, predict


class TelemetryError(ValueError):
    pass


def parse_usage(params: dict) -> dict:
    try:
        thread, turn = params["threadId"], params["turnId"]
        if not isinstance(thread,str) or not thread or not isinstance(turn,str) or not turn:
            raise ValueError("Missing identity")
        usage=params["tokenUsage"]
        last,total=usage["last"],usage["total"]
        for block in (last,total):
            for field in ("totalTokens","inputTokens","outputTokens","cachedInputTokens","reasoningOutputTokens"):
                token_count(block[field])
        window=usage.get("modelContextWindow")
        if window is not None:token_count(window,positive=True)
        return {"thread_id":thread,"turn_id":turn,"active_context_tokens":last["totalTokens"],
                "session_cumulative_tokens":total["totalTokens"],"model_context_window":window}
    except (KeyError,TypeError,ValueError) as exc:
        raise TelemetryError("Invalid tokenUsage event; never substitute cumulative totals") from exc


class Observer:
    def __init__(self, store, config, *, initial=None, configured_limit=None, scope="unknown", prefix_tokens=None):
        self.store,self.config,self.initial=store,config,initial
        self.configured_limit,self.scope,self.prefix_tokens=configured_limit,scope,prefix_tokens
        # Validate limit parameters even before first token event.
        resolve_limit(None,configured_limit,scope=scope,prefix_tokens=prefix_tokens,config=config.predictor)

    def ingest(self, event: dict):
        if not isinstance(event,dict): raise TelemetryError("Event must be an object")
        method=event.get("method")
        supported={"thread/tokenUsage/updated","turn/completed","thread/compacted","hook/started","item/completed"}
        if method not in supported:return {"ignored":True,"reason":"UNSUPPORTED_EVENT"}
        params=event.get("params")
        if not isinstance(params,dict):raise TelemetryError("Missing event params")
        thread=params.get("threadId")
        if not isinstance(thread,str) or not thread:raise TelemetryError("Missing thread identity")
        if method=="item/completed":
            item=params.get("item")
            if not isinstance(item,dict) or item.get("type")!="contextCompaction":return {"ignored":True}
        usage=parse_usage(params) if method=="thread/tokenUsage/updated" else None
        if method=="turn/completed":
            turn=params.get("turn",{}).get("id") if isinstance(params.get("turn"),dict) else None
            if not isinstance(turn,str) or not turn:raise TelemetryError("Missing completed turn id")
        elif method=="hook/started":
            run=params.get("run")
            if not isinstance(run,dict):raise TelemetryError("Invalid hook metadata")
            if run.get("eventName") not in {"preCompact","postCompact"}:return {"ignored":True}
            if not isinstance(run.get("id"),str) or not run["id"]:raise TelemetryError("Missing hook id")
        elif method in {"thread/compacted","item/completed"}:
            if not isinstance(params.get("turnId"),str) or not params["turnId"]:
                raise TelemetryError("Missing compacted turn id")
        def mutate(state):
            if state.thread_id != thread:raise TelemetryError("Cross-thread event refused")
            if state.mode not in {Mode.A.value,Mode.B.value} or state.state not in {State.NORMAL.value,State.ARMED.value}:
                raise TelemetryError("Telemetry ingestion refused during transaction/recovery")
            t=dict(state.telemetry)
            t.setdefault("samples",[]); t.setdefault("positive_deltas",[])
            t.setdefault("completed_ids",[]); t.setdefault("boundary_ids",[])
            t.setdefault("series",0); t.setdefault("precompact_samples",[])
            t.setdefault("compaction_turn_ids",[])
            # Persisted telemetry is validated before using it in arithmetic.
            try:
                for key in ("samples","positive_deltas","completed_ids","boundary_ids","precompact_samples","compaction_turn_ids"):
                    if not isinstance(t[key],list):raise ValueError()
                for d in t["positive_deltas"]:token_count(d,positive=True)
                for key in ("completed_ids","boundary_ids"):
                    if any(not isinstance(x,str) or not x for x in t[key]):raise ValueError()
                for sample in t["samples"]+([t["pending"]] if t.get("pending") is not None else []):
                    if not isinstance(sample,dict):raise ValueError()
                    if not isinstance(sample.get("turn_id"),str) or sample.get("thread_id")!=thread:raise ValueError()
                    token_count(sample.get("active_context_tokens"))
                    token_count(sample.get("session_cumulative_tokens"))
                    if sample.get("model_context_window") is not None:token_count(sample["model_context_window"],positive=True)
                if t.get("baseline") is not None:token_count(t["baseline"])
                token_count(t["series"])
            except (TypeError,ValueError):raise TelemetryError("Corrupt telemetry history")
            if usage:
                if usage["turn_id"] in t["completed_ids"]:
                    return state  # finalized/duplicate events cannot extend a completed turn
                pending=t.get("pending")
                if pending and pending["turn_id"] != usage["turn_id"]:
                    raise TelemetryError("New turn before prior completion; reconcile ordered stream")
                previous=state.last_active_context_tokens
                if previous is not None and usage["active_context_tokens"] < previous:
                    t["positive_deltas"]=[];t["series"]+=1;t["baseline"]=None
                    t["last_boundary_source"]="context_drop_observed"
                    t["last_drop_turn_id"]=usage["turn_id"]
                t["pending"]=usage
                return replace(state,last_active_context_tokens=usage["active_context_tokens"],
                               model_context_window=usage["model_context_window"],telemetry=t)
            if method=="turn/completed":
                if turn in t["completed_ids"]:return state
                pending=t.get("pending")
                if turn in t["compaction_turn_ids"]:
                    if pending and pending["turn_id"]==turn:
                        t["samples"]=(t["samples"]+[pending|{"series":t["series"],"kind":"compaction"}])[-max(16,self.config.predictor.window_size+1):]
                    t["pending"]=None;t["baseline"]=None;t["last_prediction"]=None
                    t["completed_ids"]=(t["completed_ids"]+[turn])[-256:]
                    return replace(state,telemetry=t)
                if not pending or pending["turn_id"]!=turn:
                    raise TelemetryError("Completed turn has no matching telemetry; no stale prediction")
                current=pending["active_context_tokens"]
                baseline=t.get("baseline")
                if baseline is not None:
                    token_count(baseline)
                    delta=current-baseline
                    if delta>0:t["positive_deltas"]=(t["positive_deltas"]+[delta])[-self.config.predictor.window_size:]
                    elif delta<0:
                        t["positive_deltas"]=[];t["series"]+=1
                limit=resolve_limit(pending["model_context_window"],self.configured_limit,
                                    scope=self.scope,prefix_tokens=self.prefix_tokens,config=self.config.predictor)
                decision=predict(current,pending["model_context_window"],t["positive_deltas"],limit,self.config.predictor)
                t["last_prediction"]=decision
                t["samples"]=(t["samples"]+[pending | {"series":t["series"],"kind":"conversation"}])[-max(16,self.config.predictor.window_size+1):]
                t["completed_ids"]=(t["completed_ids"]+[turn])[-256:]
                t["baseline"]=current;t["pending"]=None
                return replace(state,last_turn_id=turn,effective_auto_compact_limit=limit.tokens,
                    predicted_next_growth=decision.get("predicted_growth"),safety_buffer=decision.get("safety_buffer"),
                    risk_score=decision["risk_score"],threshold_source=limit.source,telemetry=t)
            if method=="hook/started" and params["run"]["eventName"]=="preCompact":
                key='pre:'+params['run']['id']
                if key in t["boundary_ids"]:return state
                t["precompact_samples"]=(t["precompact_samples"]+[{"active_tokens":state.last_active_context_tokens,
                    "turn_id":params.get("turnId"),"trigger":"unknown", # Hook metadata lacks trigger
                    "positive_deltas":list(t["positive_deltas"]),"prediction":t.get("last_prediction")}])[-32:]
            else:
                compact_turn=params.get("turnId")
                key='compact:'+compact_turn if compact_turn else 'post:'+params['run']['id']
                if key in t["boundary_ids"]:return state
                t["positive_deltas"]=[];t["baseline"]=None
                if not compact_turn or t.get("last_drop_turn_id")!=compact_turn:t["series"]+=1
                t["last_boundary_source"]=method;t["last_prediction"]=None
                if compact_turn:t["compaction_turn_ids"]=(t["compaction_turn_ids"]+[compact_turn])[-256:]
                pending=t.get("pending")
                # Current runtime emits usage before the compaction item. Keep that sample only
                # as a boundary sample, never as the baseline for a future conversation turn.
                keep=method=="item/completed" and pending and pending["turn_id"]==compact_turn
                if not keep:t["pending"]=None
                state=replace(state,last_active_context_tokens=state.last_active_context_tokens if keep else None,
                              model_context_window=state.model_context_window if keep else None,
                              effective_auto_compact_limit=None,predicted_next_growth=None,
                              safety_buffer=None,risk_score=None,threshold_source=None)
            t["boundary_ids"]=(t["boundary_ids"]+[key])[-256:]
            return replace(state,telemetry=t)
        state=self.store.update(mutate,initial=self.initial)
        result={"state":state.state,"mode":state.mode,"revision":state.revision,
                "prediction":state.telemetry.get("last_prediction") if method=="turn/completed" else None,
                "production_action":None}
        try:
            append_event(self.store.directory/"telemetry.jsonl",method,workspace_id=state.workspace_id,
                         thread_id=state.thread_id,turn_id=usage["turn_id"] if usage else state.last_turn_id,
                         data=usage or {"revision":state.revision,"prediction":result["prediction"]})
        except OSError:
            result["diagnostic_log_error"]=True  # authoritative state already durable
        return result
