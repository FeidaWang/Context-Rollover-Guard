"""Single hook dispatcher. Stop support is opt-in; no production registration."""
from dataclasses import replace
from pathlib import Path
from .archive import sha,ArchiveManager
from .config import Config
from .domain import State,Mode,now
from .durable import immutable_write,read_private
from .predictor import resolve_limit,predict
from .state_store import canonical,StoreError
import json


class HookError(ValueError):
    pass


def validate_event(event,state):
    if not isinstance(event,dict):raise HookError('Hook input must be an object')
    if event.get('session_id')!=state.session_id:raise HookError('Hook session mismatch')
    cwd=event.get('cwd')
    if not isinstance(cwd,str) or not Path(cwd).is_absolute() or Path(cwd).resolve()!=Path(state.cwd):
        raise HookError('Hook workspace mismatch')
    if not isinstance(event.get('turn_id'),str) or not event['turn_id']:raise HookError('Missing turn id')
    if event.get('thread_id',state.thread_id)!=state.thread_id:raise HookError('Hook thread mismatch')


def pending_answer(state):
    record=state.telemetry.get('guard',{}).get('pending_answer')
    if not isinstance(record,dict) or record.get('turn_id')!=state.last_turn_id:
        raise HookError('No exact answer for previous turn')
    if record.get('path')!=state.pending_answer_path:raise HookError('Pending answer path conflict')
    data=read_private(Path(record['path']))
    if sha(data)!=record.get('sha256'):raise HookError('Pending answer checksum mismatch')
    return data


class HookDispatcher:
    def __init__(self,store,config:Config,*,allow_warning=False,configured_limit=None,scope='unknown',
                 allow_prompt_block=False,allow_precompact_block=False,archive_root=None):
        self.store,self.config=store,config
        self.allow_warning=allow_warning
        self.allow_prompt_block=allow_prompt_block
        self.allow_precompact_block=allow_precompact_block
        self.archive_root=Path(archive_root) if archive_root is not None else None
        self.configured_limit,self.scope=configured_limit,scope

    def dispatch(self,event):
        if not self.config.context_rollover.enabled:return {}
        if not isinstance(event,dict):raise HookError('Invalid hook input')
        if event.get('hook_event_name')=='Stop':return self.stop(event)
        if event.get('hook_event_name')=='UserPromptSubmit':return self.user_prompt(event)
        if event.get('hook_event_name')=='PreCompact':return self.pre_compact(event)
        # Later handlers must be capability-gated individually; unknown events are no-ops.
        return {}

    def stop(self,event):
        current=self.store.read()
        if current is None:raise HookError('Session state unavailable')
        validate_event(event,current)
        if not isinstance(event.get('last_assistant_message'),str):
            if current.mode==Mode.B.value and current.state!=State.RECOVERY.value:
                self.store.update(lambda s:replace(s,state=State.RECOVERY.value,
                    last_turn_id=event['turn_id'],recovery_reason='LOSSLESS_ANSWER_UNAVAILABLE'))
            raise HookError('Lossless Stop answer unavailable; null is not empty')
        output={}
        def mutate(state):
            validate_event(event,state)
            turn=event['turn_id'];answer=event.get('last_assistant_message')
            if not isinstance(answer,str):raise HookError('Lossless Stop answer unavailable; null is not empty')
            data=answer.encode('utf-8')
            key=sha((turn+'\0').encode()+data)
            path=self.store.directory/('answer-'+key+'.md')
            immutable_write(path,data)
            telemetry=dict(state.telemetry);guard=dict(telemetry.get('guard',{}))
            guard['pending_answer']={'turn_id':turn,'path':str(path),'sha256':sha(data),'bytes':len(data)}
            telemetry['guard']=guard
            pending=telemetry.get('pending')
            active=window=None;deltas=list(telemetry.get('positive_deltas',[]))
            if isinstance(pending,dict) and pending.get('turn_id')==turn:
                active,window=pending['active_context_tokens'],pending['model_context_window']
                baseline=telemetry.get('baseline')
                if baseline is not None and active>baseline:deltas.append(active-baseline)
            elif state.last_turn_id==turn:
                active,window=state.last_active_context_tokens,state.model_context_window
            limit=resolve_limit(window,self.configured_limit,scope=self.scope,config=self.config.predictor)
            decision=predict(active,window,deltas,limit,self.config.predictor)
            guard['stop_prediction']=decision
            from .continuity import decide
            guard['continuity_policy']=decide(high_pressure=decision['decision']=='ARM').value
            can_warn=self.allow_warning and state.mode==Mode.B.value
            changed=replace(state,pending_answer_path=str(path),last_turn_id=turn,telemetry=telemetry)
            if can_warn and decision['decision']=='ARM':
                if changed.state==State.NORMAL.value:changed=changed.transition(State.ARMED)
                if changed.state!=State.ARMED.value:raise HookError('Cannot warn from current transaction state')
                warned=list(guard.get('warning_turn_ids',[]))
                if turn not in warned:
                    # Durable reservation before returning stdout: at-most-once warning across retry.
                    guard['warning_turn_ids']=(warned+[turn])[-256:]
                    guard['warning_delivery']='reserved_before_hook_output'
                    output['systemMessage']=(
                        '⚠ Context Rollover Guard\n下一轮可能触发上下文压缩。本轮回答已无损保存。'
                        '\n当前 surface 未启用自动切换；如需 fresh context，请先创建同一 workspace 的新任务。')
            return changed
        self.store.update(mutate)
        return output


    def _capture_prompt(self,event,state):
        validate_event(event,state)
        prompt=event.get('prompt')
        if not isinstance(prompt,str):raise HookError('Exact prompt text unavailable')
        digest=sha(prompt.encode())
        ident=sha(canonical([state.workspace_id,state.thread_id,event['turn_id'],digest]))
        path=self.store.directory/('prompt-'+ident+'.json')
        if path.exists():
            payload=json.loads(read_private(path))
            if payload.get('text')!=prompt or payload.get('sha256')!=digest or payload.get('thread_id')!=state.thread_id:
                raise HookError('Durable prompt conflict')
        else:
            payload={'schema_version':1,'submission_id':ident,'text':prompt,'sha256':digest,
                     'thread_id':state.thread_id,'old_turn_id':state.last_turn_id,
                     'submitted_turn_id':event['turn_id'],'cwd':state.cwd,'captured_at':now()}
            immutable_write(path,canonical(payload))
        return {'id':ident,'path':str(path),'sha256':digest}

    def user_prompt(self,event):
        if not self.allow_prompt_block:return {}
        output={};captured=None
        # A corrupt primary may still be inspected non-actionably. Capture in the inbox only.
        current=self.store.read()
        if current is None:raise HookError('Session state unavailable')
        if current.mode!=Mode.B.value or current.state==State.NORMAL.value:return {}
        if current.state in {State.ARMED.value, State.EMERGENCY.value} and not self.config.emergency.force_rollover_on_next_prompt:return {}
        if current.state==State.EMERGENCY.value and not self.config.emergency.force_rollover_on_next_prompt:return {}
        if current.state==State.RECOVERY.value:
            validate_event(event,current)
            with self.store._lock():captured=self._capture_prompt(event,current)
            return {'decision':'block','reason':'CRG 已保存本条输入，状态需要恢复；未执行转发。持久化位置：'+captured['path']}
        def mutate(state):
            nonlocal captured
            validate_event(event,state)
            if state.mode!=Mode.B.value or state.state==State.NORMAL.value:return state
            if state.state==State.EMERGENCY.value and not self.config.emergency.force_rollover_on_next_prompt:return state
            captured=self._capture_prompt(event,state)  # before answer reads, snapshots, or future thread calls
            t=dict(state.telemetry);guard=dict(t.get('guard',{}));t['guard']=guard
            submissions=dict(guard.get('submissions',{}));guard['submissions']=submissions
            submissions[captured['id']]=captured
            output.update(decision='block',reason='CRG 已保存本条输入。当前 surface 未自动切换，请从同一 workspace 的 fresh task 恢复。')
            active=guard.get('active_submission_id')
            if active:
                if active!=captured['id']:output['reason']='CRG 已另存本条输入；已有交接等待恢复，未重复转发。'
                return replace(state,telemetry=t)
            try:
                if state.state not in {State.ARMED.value,State.EMERGENCY.value}:raise HookError('Unexpected transaction state')
                if self.archive_root is None:raise HookError('Archive root not configured')
                answer=pending_answer(state)
                folder=ArchiveManager(self.archive_root).prepare(state,event['prompt'],answer)
                guard['active_submission_id']=captured['id'];guard['archive_dir']=str(folder)
                changed=replace(state,telemetry=t,rollover_id=folder.name)
                changed=changed.transition(State.PREPARING,evidence={'prompt_persisted':True})
                output['reason']+=' Handoff: '+str(folder/'handoff.md')
                return changed
            except (OSError,ValueError,StoreError) as exc:
                guard['preparation_error']=type(exc).__name__
                output['reason']='CRG 已持久化本条输入，但交接未完成，需要恢复；没有转发或归档旧任务。'
                return replace(state,telemetry=t,state=State.RECOVERY.value,recovery_reason='ARCHIVE_PREPARATION_FAILED')
        try:self.store.update(mutate,evidence={'prompt_persisted':True})
        except (OSError,StoreError):
            if not captured:raise
            return {'decision':'block','reason':'CRG 已持久化本条输入，但状态写入失败；请恢复。位置：'+captured['path']}
        return output

    def pre_compact(self,event):
        if event.get('trigger')!='auto':return {}
        output={}
        block=self.allow_precompact_block and self.config.emergency.block_auto_compact
        def mutate(state):
            validate_event(event,state)
            if state.mode!=Mode.B.value:return state
            key=sha(canonical([state.thread_id,event['turn_id'],'auto']))
            snapshot=self.store.directory/('emergency-'+key+'.json')
            if not snapshot.exists():
                immutable_write(snapshot,canonical({'schema_version':1,'trigger':'auto','turn_id':event['turn_id'],
                                'thread_id':state.thread_id,'created_at':now(),'state':state.to_dict()}))
            else:
                saved=json.loads(read_private(snapshot))
                if saved.get('thread_id')!=state.thread_id or saved.get('turn_id')!=event['turn_id']:
                    raise HookError('Emergency snapshot conflict')
            saved=json.loads(read_private(snapshot))
            t=dict(state.telemetry);guard=dict(t.get('guard',{}));t['guard']=guard
            guard['emergency_snapshot']=str(snapshot);guard['force_rollover_on_next_prompt']=self.config.emergency.force_rollover_on_next_prompt
            guard['prediction_miss']=saved['state']['state']==State.NORMAL.value
            if not block and not self.config.emergency.force_rollover_on_next_prompt:
                guard['continuity_policy']='OBSERVE'
                return replace(state,telemetry=t)
            target=State.EMERGENCY if state.state in {State.NORMAL.value,State.ARMED.value,State.EMERGENCY.value} else State.RECOVERY
            changed=replace(state,telemetry=t).transition(target)
            if block:output.update({'continue':False,'stopReason':'CRG 已保存紧急状态；需要在同 workspace 的 fresh task 恢复。'})
            return changed
        current=self.store.read()
        if current is None or current.mode!=Mode.B.value:return {}
        validate_event(event,current)
        try:self.store.update(mutate)
        except (OSError,ValueError,StoreError):
            if block:return {'continue':False,'stopReason':'CRG 无法确认紧急快照已完成；暂停压缩并要求恢复。'}
            raise
        return output
