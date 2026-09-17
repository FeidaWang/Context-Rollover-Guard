"""Lossless, immutable, restartable answer/prompt/handoff archives. No thread APIs."""
import hashlib
import json
from pathlib import Path
from .domain import now
from .durable import private_directory,exclusive_lock,immutable_write,read_private
from .handoff import workspace_snapshot,build_handoff
from .state_store import canonical

FILES={'answer.md','prompt.json','metadata.json','handoff.md','handoff.json'}


def sha(data:bytes):return hashlib.sha256(data).hexdigest()


def rollover_id(workspace_id:str,thread:str,turn:str,prompt:str):
    if not all(isinstance(v,str) and v for v in (workspace_id,thread,turn)) or not isinstance(prompt,str):
        raise ValueError('Invalid rollover identity')
    return 'crg_'+sha(canonical([workspace_id,thread,turn,sha(prompt.encode('utf-8'))]))


class ArchiveManager:
    def __init__(self,root:Path,*,fault=None):
        self.root=private_directory(root);self.fault=fault or (lambda step:None)

    def prepare(self,state,prompt:str,answer:bytes):
        state.validate()
        if not isinstance(prompt,str) or not isinstance(answer,bytes):raise ValueError('Exact prompt/answer required')
        if not state.last_turn_id:raise ValueError('Previous answer turn required')
        rid=rollover_id(state.workspace_id,state.thread_id,state.last_turn_id,prompt)
        directory=private_directory(self.root/rid)
        with exclusive_lock(directory):
            prompt_path=directory/'prompt.json'
            if prompt_path.exists():
                captured=json.loads(read_private(prompt_path))
                if captured.get('text')!=prompt or captured.get('sha256')!=sha(prompt.encode()):
                    raise ValueError('Pending prompt integrity conflict')
                if captured.get('old_thread_id')!=state.thread_id:raise ValueError('Prompt thread mismatch')
            else:
                captured={'text':prompt,'sha256':sha(prompt.encode()),'captured_at':now(),
                          'old_thread_id':state.thread_id,'old_turn_id':state.last_turn_id}
                immutable_write(prompt_path,canonical(captured))
            self.fault('prompt_persisted')
            immutable_write(directory/'answer.md',answer);self.fault('answer_archived')
            meta_path=directory/'metadata.json'
            if meta_path.exists():metadata=json.loads(read_private(meta_path))
            else:
                workspace=workspace_snapshot(Path(state.cwd))
                metadata={'schema_version':2,'rollover_id':rid,'old_thread_id':state.thread_id,
                    'old_turn_id':state.last_turn_id,'session_id':state.session_id,'cwd':state.cwd,
                    'repo_root':workspace['repo_root'],'git_branch':workspace['git_branch'],
                    'git_head':workspace['git_head'],'model':state.model,'workspace':workspace,
                    'context_usage':state.last_active_context_tokens,
                    'predictor_snapshot':state.telemetry.get('last_prediction'),
                    'created_at':captured['captured_at']}
                immutable_write(meta_path,canonical(metadata))
            if metadata.get('rollover_id')!=rid or metadata.get('cwd')!=state.cwd:
                raise ValueError('Archive metadata identity conflict')
            source={k:metadata[k] for k in ('rollover_id','old_thread_id','old_turn_id')}
            handoff,data=build_handoff(source,metadata['workspace'],directory,
                prompt_hash=sha(read_private(prompt_path)), answer_hash=sha(answer), version=metadata['schema_version'])
            immutable_write(directory/'handoff.md',handoff.encode('utf-8'))
            immutable_write(directory/'handoff.json',canonical(data));self.fault('handoff_written')
            checks={name:sha(read_private(directory/name)) for name in sorted(FILES)}
            checksum=''.join(checks[name]+'  '+name+'\n' for name in sorted(checks)).encode()
            immutable_write(directory/'integrity.sha256',checksum)
            immutable_write(directory/'READY.json',canonical({'schema_version':1,'rollover_id':rid,
                'integrity_sha256':sha(checksum),'prepared_at':captured['captured_at']}))
            self.fault('archive_ready')
            self.verify(directory)
        return directory

    def verify(self,directory:Path):
        directory=directory.absolute()
        if directory.parent!=self.root or not directory.name.startswith('crg_'):
            raise ValueError('Archive outside configured root')
        if directory.is_symlink():raise ValueError('Archive symlink refused')
        ready=json.loads(read_private(directory/'READY.json'))
        checksum=read_private(directory/'integrity.sha256')
        if ready.get('schema_version')!=1 or ready.get('rollover_id')!=directory.name or ready.get('integrity_sha256')!=sha(checksum):
            raise ValueError('Archive ready marker invalid')
        entries={}
        for line in checksum.decode('ascii').splitlines():
            digest,name=line.split('  ',1)
            if name not in FILES or name in entries:raise ValueError('Invalid integrity manifest')
            entries[name]=digest
        if set(entries)!=FILES:raise ValueError('Incomplete archive manifest')
        for name,digest in entries.items():
            if sha(read_private(directory/name))!=digest:raise ValueError('Archive integrity failure')
        prompt=json.loads(read_private(directory/'prompt.json'))
        if sha(prompt['text'].encode())!=prompt['sha256']:raise ValueError('Prompt checksum mismatch')
        handoff=json.loads(read_private(directory/'handoff.json'))
        if handoff.get('schema_version') not in {1,2}:raise ValueError('Unsupported handoff version')
        if handoff['schema_version']==2:
            for key,name in [('user_prompt','prompt.json'),('previous_answer','answer.md')]:
                if handoff.get(key)!={'path':name,'sha256':entries[name]}:raise ValueError('Handoff data pointer mismatch')
            for instruction in handoff.get('instruction_sources',[]):
                if instruction.get('kind')!='user' and instruction.get('replayable') is not False:
                    raise ValueError('Non-user instruction replay forbidden')
        return {'rollover_id':directory.name,'verified':True,'files':sorted(FILES)}
