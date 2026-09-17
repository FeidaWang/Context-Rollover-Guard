"""Positive-only reconciliation. Absence never authorizes a resend."""
from .domain import State
from .durable import exclusive_lock
from .coordinator import TransactionError


def reconcile_forward(coordinator,rid):
    directory=coordinator._directory(rid)
    with exclusive_lock(directory):
        prepared,source,prompt,settings=coordinator._context(directory)
        existing=coordinator._read(directory,'accepted')
        if existing:return {'state':State.ARCHIVING.value,'evidence':existing}
        intent=coordinator._read(directory,'forward-intent')
        started=coordinator._read(directory,'started')
        if not intent or not started:return {'state':State.RECOVERY.value,'reason':'NO_KNOWN_FORWARD_INTENT'}
        settings.verify_new_thread(started)
        tid=started['thread']['id']
        if tid==source.thread_id or intent['new_thread_id']!=tid:raise TransactionError('Recovery thread mismatch')
        response=coordinator.client.request('thread/read',{'threadId':tid,'includeTurns':True})
        thread=response['thread']
        if thread['id']!=tid or thread['cwd']!=source.cwd:raise TransactionError('Readback binding mismatch')
        matches=[(turn,item) for turn in thread['turns'] for item in turn['items']
                 if item.get('type')=='userMessage' and item.get('clientId')==prepared['client_message_id']]
        if len(matches)!=1:return {'state':State.RECOVERY.value,'reason':'ACCEPTANCE_ABSENT_OR_DUPLICATED','automatic_resend':False}
        turn,item=matches[0]
        if item.get('content')!=[{'type':'text','text':prompt}] and not (
            len(item.get('content',[]))==1 and item['content'][0].get('type')=='text'
            and item['content'][0].get('text')==prompt
            and set(item['content'][0])<={'type','text','text_elements'}):
            return {'state':State.RECOVERY.value,'reason':'CONTENT_MISMATCH','automatic_resend':False}
        if turn.get('status') not in {'inProgress','completed'} or not turn.get('id'):
            return {'state':State.RECOVERY.value,'reason':'TURN_NOT_SUCCESSFULLY_ACCEPTED','automatic_resend':False}
        receipt={'thread_id':tid,'turn_id':turn['id'],'client_message_id':prepared['client_message_id'],
                 'prompt_sha256':prepared['prompt_sha256'],'source':'positive thread/read reconciliation'}
        coordinator._write(directory,'accepted',receipt)
        return {'state':State.ARCHIVING.value,'evidence':receipt}


def transaction_status(coordinator,rid):
    directory=coordinator._directory(rid)
    with exclusive_lock(directory):
        coordinator._context(directory)
        if coordinator._read(directory,'committed'):return coordinator._read(directory,'committed')
        for intent,receipt in [('archive-intent','archived'),('forward-intent','accepted'),('start-intent','started')]:
            if coordinator._read(directory,intent) and not coordinator._read(directory,receipt):
                return {'state':State.RECOVERY.value,'operation':intent,'automatic_resend':False}
        if coordinator._read(directory,'recovery-settings'):return {'state':State.RECOVERY.value,'reason':'SETTINGS_MISMATCH'}
        if coordinator._read(directory,'accepted'):state=State.ARCHIVING
        elif coordinator._read(directory,'started'):state=State.FORWARDING
        elif coordinator._read(directory,'start-intent'):state=State.STARTING
        else:state=State.PREPARING
        return {'state':state.value,'rollover_id':rid}


def reconcile_archive(coordinator,rid,*,max_pages=20):
    """Only positive archived-list membership can resolve an unknown archive receipt."""
    directory=coordinator._directory(rid)
    with exclusive_lock(directory):
        prepared,source,prompt,settings=coordinator._context(directory)
        accepted=coordinator._read(directory,'accepted')
        intent=coordinator._read(directory,'archive-intent')
        if not accepted or not intent:return {'state':State.RECOVERY.value,'reason':'NO_CONFIRMED_FORWARD_AND_ARCHIVE_INTENT'}
        if coordinator._read(directory,'archived'):return {'state':State.ARCHIVING.value,'archive_confirmed':True}
        cursor=None;seen=set()
        for _ in range(max_pages):
            params={'archived':True,'cwd':source.cwd,'limit':100}
            if cursor:params['cursor']=cursor
            result=coordinator.client.request('thread/list',params)
            if any(t.get('id')==source.thread_id and t.get('cwd')==source.cwd for t in result['data']):
                coordinator._write(directory,'archived',{'old_thread_id':source.thread_id})
                return {'state':State.ARCHIVING.value,'archive_confirmed':True}
            cursor=result.get('nextCursor')
            if not cursor or cursor in seen:break
            seen.add(cursor)
        return {'state':State.RECOVERY.value,'reason':'ARCHIVE_UNCONFIRMED','automatic_resend':False}
