"""Repo-local MODE_B binding. No thread RPC, UI mutation or transcript copying."""
from dataclasses import replace
import json,os,stat
from pathlib import Path
from .config import load_config
from .domain import SessionState,Mode,State
from .hooks import HookDispatcher,HookError
from .state_store import StateStore
from .durable import regular_file


def transcript_events(path,*,session,cwd,version=None,allowed_root, binding=None):
    """Project numeric records from the exact Hook-supplied transcript, never glob sessions."""
    path=Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(allowed_root.resolve()):
        raise ValueError('Transcript path outside native session storage')
    samples={};order=[];completed=set();bound=False;current=None;window=None;valid=set();compacted=set()
    with regular_file(path,private=False) as stream:
        st=os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or st.st_size>256*1024*1024:raise ValueError('Unsupported transcript file')
        consumed=0
        while True:
            raw=stream.readline(1024*1024+1)
            if not raw:break
            consumed+=len(raw)
            if len(raw)>1024*1024 or consumed>256*1024*1024:raise ValueError('Transcript read limit exceeded')
            if not raw.endswith(b'\n'):break  # unfinished final record is not evidence
            row=json.loads(raw);kind=row.get('type');p=row.get('payload',{})
            if not isinstance(p,dict):continue
            if kind=='session_meta':
                if p.get('id')!=session or version is not None and p.get('cli_version')!=version:raise ValueError('Transcript session/version mismatch')
                if binding is not None:
                    binding['session_creation_version'] = p.get('cli_version')
                    binding['current_execution_version'] = None
                bound=True
            elif kind=='event_msg' and p.get('type')=='task_started':
                current=p.get('turn_id');window=p.get('model_context_window')
            elif kind=='turn_context':
                current=p.get('turn_id')
                if isinstance(p.get('cwd'),str) and Path(p['cwd']).resolve()==cwd:valid.add(current)
            elif kind in {'compacted','context_compaction'} or kind=='event_msg' and p.get('type')=='context_compacted':
                samples.clear();order.clear();completed.clear();compacted.add(current)
            elif kind=='token_usage_record' and p.get('thread_id')==session and p.get('turn_id') in valid:
                turn=p['turn_id']
                if turn in compacted:continue
                def tokens(block):
                    return {target:block[source] for source,target in [('total_tokens','totalTokens'),('input_tokens','inputTokens'),
                        ('output_tokens','outputTokens'),('cached_input_tokens','cachedInputTokens'),('reasoning_output_tokens','reasoningOutputTokens')]}
                event={'method':'thread/tokenUsage/updated','params':{'threadId':session,'turnId':turn,
                    'tokenUsage':{'last':tokens(p['usage']),'total':tokens(p['thread_token_usage']),
                                  'modelContextWindow':window if current==turn else None}}}
                if turn not in samples:order.append(turn)
                samples[turn]=event
            elif kind=='event_msg' and p.get('type')=='task_complete':completed.add(p.get('turn_id'))
    if not bound:raise ValueError('Missing transcript identity')
    result=[]
    for turn in order[-128:]:
        result.append(samples[turn])
        if turn in completed:result.append({'method':'turn/completed','params':{'threadId':session,'turn':{'id':turn,'status':'completed'}}})
    return result


def dispatch_repo(event,workspace,*,native_home=None):
    workspace=Path(workspace).resolve();config=load_config(workspace)
    if not config.context_rollover.enabled or config.context_rollover.mode!='MODE_B':return {}
    if config.continuity.policy=='observe':return {}
    if not isinstance(event,dict) or Path(event.get('cwd','')).resolve()!=workspace:raise HookError('Repo Hook cwd mismatch')
    session=event.get('session_id')
    if not isinstance(session,str) or not session:raise HookError('Missing runtime session identity')
    archive_root,state_root=config.paths(workspace)
    store=StateStore(state_root,workspace,session)
    if store.read() is None:store.update(lambda s:s,initial=replace(SessionState.create(workspace,session,session),mode=Mode.B.value))
    name=event.get('hook_event_name');state=store.read()
    if name=='SessionStart':return {}
    if name=='PostCompact':
        if state.state in {State.NORMAL.value,State.ARMED.value}:
            store.update(lambda s:replace(s,last_active_context_tokens=None,telemetry={**s.telemetry,'positive_deltas':[],
                'baseline':None,'pending':None,'series':s.telemetry.get('series',0)+1}))
        return {}
    if name=='Stop' and state.state in {State.NORMAL.value,State.ARMED.value}:
        status='UNAVAILABLE';events=[]
        binding={'session_creation_version': None, 'current_execution_version': None,
                 'current_runtime_status': 'UNKNOWN'}
        try:
            home=Path(native_home) if native_home is not None else Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
            if event.get('transcript_path'):
                events=transcript_events(event['transcript_path'],session=session,cwd=workspace,allowed_root=home/'sessions',binding=binding)
            # Hook payload provides no independently verified current process identity.
            # Historical numeric records cannot authorize current pressure or actions.
            if events:status='OBSERVED_HISTORICAL_RECORD'
        except (OSError,ValueError,KeyError,RuntimeError):status='UNAVAILABLE_OR_UNVERIFIED'
        store.update(lambda s:replace(s,last_active_context_tokens=None,model_context_window=None,
            telemetry={**s.telemetry,'pending':None,'repo_adapter':{'telemetry_status':status,'source':'native token_usage_record.usage',**binding}}))
    # A configured mode or cached transcript version does not verify interception.
    # This adapter has no current-session interception contract; retain snapshots only.
    handler=HookDispatcher(store,config,allow_warning=False,allow_prompt_block=False,
                           allow_precompact_block=False,archive_root=archive_root)
    return handler.dispatch(event)
