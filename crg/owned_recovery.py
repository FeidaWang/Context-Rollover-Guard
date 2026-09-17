"""Positive completion reconciliation for an owned run; never submits or archives."""
import json
from pathlib import Path
from .durable import read_private, immutable_write, exclusive_lock
from .state_store import canonical, StateStore
from .hooks import pending_answer


def reconcile_run(directory, client, config):
    directory = Path(directory).absolute()
    states = config.paths(client.workspace)[1]
    if any(p.is_symlink() for p in [directory, *directory.parents]):
        raise ValueError('Symlink run journal refused')
    if directory.resolve().parent != (states / 'owned-runs').resolve():
        raise ValueError('Run journal must belong to this workspace')
    def read(name):
        return json.loads(read_private(directory / (name + '.json')))
    def blocked(reason):
        return {'state': 'RECOVERY_REQUIRED', 'reason': reason, 'automatic_resend': False}
    with exclusive_lock(directory, timeout=.1):
        started = read('started')
        if started['cwd'] != str(client.workspace):
            raise ValueError('Workspace mismatch')
        thread = started['thread']['id']
        paths = sorted(directory.glob('input-??????.json'))
        for index, path in enumerate(paths, 1):
            key = f'input-{index:06d}'
            if path.stem != key:
                raise ValueError('Input sequence gap')
            source = read(key)
            if source['thread_id'] != thread:
                raise ValueError('Input route mismatch')
            route_path = directory / (key + '-route.json')
            if route_path.exists():
                route = read(key + '-route')
                if route['state'] != 'NORMAL' or route['old_thread_id'] != thread:
                    return blocked('TRANSACTION_RECONCILIATION_REQUIRED')
                thread = route['new_thread_id']
            if (directory / (key + '-completed.json')).exists():
                receipt = read(key + '-completed')
                if receipt['threadId'] != thread or receipt['turn']['status'] != 'completed':
                    return blocked('INVALID_OR_FAILED_COMPLETION')
                continue
            if index != len(paths):
                return blocked('UNFINISHED_INPUT_NOT_LAST')
            if (directory / (key + '-transaction.json')).exists():
                if not route_path.exists():
                    return blocked('TRANSACTION_RECONCILIATION_REQUIRED')
                rid = read(key + '-transaction')['rollover_id']
                client_id = rid
                accepted_turn = route['accepted_turn_id']
            else:
                if not (directory / (key + '-intent.json')).exists():
                    return blocked('NO_SUBMISSION_INTENT')
                intent = read(key + '-intent')
                if intent['threadId'] != thread or intent['input'] != [{'type': 'text', 'text': source['text']}]:
                    raise ValueError('Submission intent mismatch')
                client_id = intent['clientUserMessageId']
                accepted_turn = None
                if (directory / (key + '-accepted.json')).exists():
                    accepted = read(key + '-accepted')
                    if accepted['thread_id'] != thread:
                        raise ValueError('Acceptance route mismatch')
                    accepted_turn = accepted['turn_id']
            native = client.request('thread/read', {'threadId': thread, 'includeTurns': True})['thread']
            if native['id'] != thread or native['cwd'] != str(client.workspace):
                raise ValueError('Native readback identity mismatch')
            matches = [(t, i) for t in native['turns'] for i in t['items']
                       if i.get('type') == 'userMessage' and i.get('clientId') == client_id]
            if len(matches) != 1:
                return blocked('ACCEPTANCE_ABSENT_OR_DUPLICATED')
            turn, item = matches[0]
            content = item.get('content', [])
            if len(content) != 1 or content[0].get('type') != 'text' or content[0].get('text') != source['text'] or set(content[0]) - {'type', 'text', 'text_elements'}:
                return blocked('CONTENT_MISMATCH')
            if accepted_turn is not None and turn['id'] != accepted_turn:
                return blocked('ACCEPTED_TURN_MISMATCH')
            if turn['status'] != 'completed':
                return blocked('TURN_NOT_COMPLETED')
            state = StateStore(states, client.workspace, thread).read()
            if state is None or state.last_turn_id != turn['id']:
                return blocked('NATIVE_STOP_UNAVAILABLE')
            answer = pending_answer(state).decode('utf-8')
            finals = [i['text'] for i in turn['items'] if i.get('type') == 'agentMessage' and i.get('phase') == 'final_answer']
            if finals != [answer]:
                return blocked('FINAL_ANSWER_MISMATCH_OR_UNAVAILABLE')
            # Install completion only after every independent binding is verified.
            immutable_write(directory / (key + '-completed.json'), canonical({'threadId': thread, 'turn': turn}))
            immutable_write(directory / (key + '-reconciled.json'), canonical({'source': 'positive thread/read and native Stop', 'turn_id': turn['id']}))
        return {'state': 'READY_TO_RESUME', 'thread_id': thread, 'journal': str(directory), 'automatic_resend': False}
