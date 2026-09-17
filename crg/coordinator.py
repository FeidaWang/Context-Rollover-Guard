"""Owned-client rollover with immutable intents/receipts; never retries unknown acceptance.

The transaction journal is authoritative after prepare. SessionState is the immutable source
snapshot, not the mutable identity of the new thread. No Desktop attachment is implied.
"""
from dataclasses import replace
import json
from pathlib import Path
from .appserver import ExecutionSettings
from .archive import ArchiveManager,sha
from .domain import State,SessionState
from .durable import private_directory,exclusive_lock,immutable_write,read_private
from .hooks import pending_answer
from .state_store import canonical


class TransactionError(RuntimeError):pass


class Coordinator:
    def __init__(self,root,archives,client,*,owned_surface=False,fault=None):
        if not owned_surface:raise TransactionError('An explicitly owned client surface is required')
        self.root=private_directory(Path(root));self.archives=ArchiveManager(Path(archives))
        self.client=client;self.fault=fault or (lambda step:None)

    def _write(self,directory,name,payload):
        data=canonical(payload)
        immutable_write(directory/(name+'.json'),canonical({'schema_version':1,'payload':payload,'sha256':sha(data)}))
        self.fault(name+':durable')
        # Best-effort projection only; journal receipts are the sole transaction authority.
        if directory.name.startswith('crg_'):
            try:
                from .logging import append_event
                source=payload.get('source') if name=='prepared' else (self._read(directory,'prepared') or {}).get('source')
                if isinstance(source,dict):
                    event={'prepared':'handoff_written','started':'thread_started','accepted':'prompt_forwarded',
                           'archived':'old_thread_archived','committed':'rollover_committed'}.get(name,name)
                    append_event(directory/'events.jsonl',event,workspace_id=source['workspace_id'],
                        thread_id=source['thread_id'],turn_id=source['last_turn_id'],rollover_id=directory.name,
                        data={'journal_record':name})
            except (OSError,ValueError,KeyError):pass

    def _read(self,directory,name):
        path=directory/(name+'.json')
        if not path.exists():return None
        envelope=json.loads(read_private(path))
        if envelope.get('schema_version')!=1:raise TransactionError('Unsupported journal version')
        payload=envelope['payload']
        if envelope['sha256']!=sha(canonical(payload)):raise TransactionError('Journal integrity failure')
        return payload

    def _directory(self,rid):
        if not isinstance(rid,str) or len(rid)!=68 or not rid.startswith('crg_') or any(c not in '0123456789abcdef' for c in rid[4:]):
            raise TransactionError('Invalid transaction identifier')
        return private_directory(self.root/rid)

    def prepare(self,state:SessionState,prompt:str,settings:ExecutionSettings):
        state.validate()
        if state.state not in {State.ARMED.value,State.EMERGENCY.value,State.PREPARING.value}:
            raise TransactionError('Source is not armed for rollover')
        if Path(state.cwd)!=self.client.workspace or settings.values['cwd']!=state.cwd:
            raise TransactionError('Owned workspace mismatch')
        # Validate reconstructibility before performing any thread operations.
        settings.thread_params('')
        archive=self.archives.prepare(state,prompt,pending_answer(state))
        directory=self._directory(archive.name)
        # One immutable source-thread claim prevents competing rollovers for different prompts.
        # The second prompt is already durable in its archive before this conflict is reported.
        with exclusive_lock(self.root):
            key='source-'+sha(canonical([state.workspace_id,state.thread_id]))
            claimed=self._read(self.root,key)
            if claimed is not None and claimed['rollover_id']!=archive.name:
                raise TransactionError('Source thread already claimed; second prompt retained in archive')
            if claimed is None:self._write(self.root,key,{'rollover_id':archive.name})
        with exclusive_lock(directory):
            initial=self._read(directory,'prepared')
            payload={'source':state.to_dict(),'settings':settings.values,'archive':str(archive),
                     'prompt_sha256':sha(prompt.encode()),'client_message_id':archive.name}
            if initial is not None:
                if initial!=payload:raise TransactionError('Transaction preparation conflict')
            else:self._write(directory,'prepared',payload)
        return archive.name

    def _context(self,directory):
        prepared=self._read(directory,'prepared')
        if prepared is None:raise TransactionError('Transaction not prepared')
        source=SessionState(**prepared['source']).validate()
        claim=self._read(self.root,'source-'+sha(canonical([source.workspace_id,source.thread_id])))
        if claim is None or claim.get('rollover_id')!=directory.name:raise TransactionError('Source claim mismatch')
        archive=Path(prepared['archive']);self.archives.verify(archive)
        if archive.name!=directory.name or source.cwd!=str(self.client.workspace):raise TransactionError('Transaction binding mismatch')
        prompt=json.loads(read_private(archive/'prompt.json'))
        if sha(prompt['text'].encode())!=prepared['prompt_sha256'] or prompt['old_thread_id']!=source.thread_id:
            raise TransactionError('Prompt binding mismatch')
        return prepared,source,prompt['text'],ExecutionSettings(prepared['settings'])

    def _blocked(self,directory,operation):
        self._write(directory,'recovery-'+operation,{'operation':operation,'reason':'ACCEPTANCE_OR_RECEIPT_UNCONFIRMED'})
        return {'state':State.RECOVERY.value,'operation':operation,'rollover_id':directory.name,
                'automatic_resend':False,'old_thread_retained':operation!='archive'}

    def run(self,rid):
        directory=self._directory(rid)
        with exclusive_lock(directory):
            prepared,source,prompt,settings=self._context(directory)
            committed=self._read(directory,'committed')
            if committed:return committed
            started=self._read(directory,'started')
            if started is None:
                if self._read(directory,'start-intent'):return self._blocked(directory,'start')
                params=settings.thread_params(read_private(Path(prepared['archive'])/'handoff.md').decode())
                params['ephemeral']=False
                self.client.schema.validate('thread/start',params)
                self._write(directory,'start-intent',{'params_sha256':sha(canonical(params))})
                try:
                    response=self.client.request('thread/start',params)
                    self.fault('start:accepted')
                    # Save the id/response even when settings validation will subsequently fail.
                    self._write(directory,'started',response);started=response
                except Exception:return self._blocked(directory,'start')
            try:
                settings.verify_new_thread(started)
                new=started['thread']['id']
                if new==source.thread_id or started['thread'].get('turns')!=[]:raise TransactionError('Thread is not fresh')
                if started['thread'].get('cwd')!=source.cwd:raise TransactionError('Thread cwd differs')
            except (ValueError,KeyError,TransactionError):return self._blocked(directory,'settings')
            accepted=self._read(directory,'accepted')
            if accepted is None:
                if self._read(directory,'forward-intent'):return self._blocked(directory,'forward')
                params=settings.turn_params(new,prompt,prepared['client_message_id'])
                self.client.schema.validate('turn/start',params)
                self._write(directory,'forward-intent',{'new_thread_id':new,'client_message_id':prepared['client_message_id'],
                                                       'prompt_sha256':prepared['prompt_sha256']})
                try:
                    response=self.client.request('turn/start',params)
                    self.fault('forward:accepted')
                    turn=response['turn']
                    if not isinstance(turn.get('id'),str) or not turn['id'] or turn.get('status') not in {'inProgress','completed'}:
                        raise TransactionError('Turn acceptance is not confirmed')
                    accepted={'thread_id':new,'turn_id':turn['id'],'client_message_id':prepared['client_message_id'],
                              'prompt_sha256':prepared['prompt_sha256'],'source':'turn/start response'}
                    self._write(directory,'accepted',accepted)
                except Exception:return self._blocked(directory,'forward')
            if accepted['thread_id']!=new or accepted['prompt_sha256']!=prepared['prompt_sha256']:
                raise TransactionError('Acceptance receipt mismatch')
            archived=self._read(directory,'archived')
            if archived is None:
                if self._read(directory,'archive-intent'):return self._blocked(directory,'archive')
                self._write(directory,'archive-intent',{'old_thread_id':source.thread_id,'accepted_turn_id':accepted['turn_id']})
                try:
                    self.client.request('thread/archive',{'threadId':source.thread_id})
                    self.fault('archive:accepted')
                    self._write(directory,'archived',{'old_thread_id':source.thread_id})
                except Exception:return self._blocked(directory,'archive')
            result={'state':State.NORMAL.value,'rollover_id':rid,'old_thread_id':source.thread_id,
                    'new_thread_id':new,'accepted_turn_id':accepted['turn_id'],'old_thread_archived':True,
                    'surface':'owned-app-server','desktop_switched':False}
            self._write(directory,'committed',result)
            return result
