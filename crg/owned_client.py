"""Sequential owned transport for installed, trusted repo-local CRG Hooks.

The native Hooks remain the authority for answer capture and predictor state.
This client owns only input routing and the existing rollover transaction.
"""
from pathlib import Path
import json
import time
import uuid
import math
from .appserver import ExecutionSettings
from .coordinator import Coordinator
from .durable import private_directory, immutable_write, read_private, exclusive_lock
from .state_store import StateStore, canonical
from .domain import State
from .hooks import pending_answer


class OwnedSession:
    def __init__(self, client, config, *, timeout=300, emit=None, approve=None):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be finite and positive")
        self.client, self.config = client, config
        self.timeout, self.emit, self.approve = timeout, emit or (lambda event: None), approve
        archives, self.states = config.paths(client.workspace)
        self.root = private_directory(self.states / 'owned-runs' / uuid.uuid4().hex)
        self.coordinator = Coordinator(self.states / 'transactions', archives, client, owned_surface=True)
        self.thread = self.settings = None
        self.blocked = False
        self.sequence = 0

    def record(self, name, value):
        immutable_write(self.root / (name + '.json'), canonical(value))

    def start(self, params):
        if self.thread is not None or self.blocked:
            raise ValueError('Session already started or requires recovery')
        params = dict(params, cwd=str(self.client.workspace), ephemeral=False)
        self.record('start-intent', params)
        try:
            response = self.client.request('thread/start', params)
            self.record('started', response)
            self.settings = ExecutionSettings.from_start(response)
            self.settings.thread_params('')  # fail before accepting input if unreconstructible
            self.thread = response['thread']['id']
            if response['thread'].get('cwd') != str(self.client.workspace):
                raise ValueError('Runtime workspace mismatch')
        except BaseException:
            self.blocked = True
            raise
        self.emit({'type': 'ready', 'thread_id': self.thread, 'journal': str(self.root)})

    def resume(self, directory):
        directory = Path(directory).absolute()
        if any(p.is_symlink() for p in [directory, *directory.parents]):
            raise ValueError("Symlink run journal refused")
        runs = (self.states / 'owned-runs').resolve()
        if directory.parent != runs or directory.is_symlink():
            raise ValueError('Resume journal must belong to this workspace')
        started = json.loads(read_private(directory / 'started.json'))
        settings = ExecutionSettings.from_start(started)
        if settings.values['cwd'] != str(self.client.workspace):
            raise ValueError('Resume workspace mismatch')
        thread = started['thread']['id']
        inputs = sorted(directory.glob('input-??????.json'))
        for index, path in enumerate(inputs, 1):
            if path.stem != f'input-{index:06d}':
                raise ValueError('Non-contiguous input journal')
            completed = directory / (path.stem + '-completed.json')
            if not completed.exists():
                raise ValueError('Unfinished input requires reconciliation; never replay')
            receipt = json.loads(read_private(completed))
            if receipt['turn']['status'] != 'completed':
                raise ValueError('Failed input requires recovery')
            route = directory / (path.stem + '-route.json')
            if route.exists():
                result = json.loads(read_private(route))
                if result['state'] != State.NORMAL.value or result['old_thread_id'] != thread:
                    raise ValueError('Invalid route receipt')
                thread = result['new_thread_id']
            if receipt['threadId'] != thread:
                raise ValueError('Completion route mismatch')
        if inputs:
            state = StateStore(self.states, self.client.workspace, thread).read()
            if state is None or state.last_turn_id != receipt['turn']['id']:
                raise ValueError('Last native Stop requires recovery')
            pending_answer(state)
        params = settings.thread_params('')
        params.pop('developerInstructions', None)
        params['threadId'] = thread
        response = self.client.request('thread/resume', params)
        settings.verify_new_thread(response)
        if response['thread']['id'] != thread:
            raise ValueError('Resumed thread identity mismatch')
        self.root, self.thread, self.settings = directory, thread, settings
        self.sequence = len(inputs)
        self.emit({'type': 'ready', 'thread_id': thread, 'journal': str(directory), 'resumed': True})

    def submit(self, prompt):
        if self.blocked or not self.thread:
            raise ValueError('Session requires recovery; no automatic resend')
        if not isinstance(prompt, str):
            raise ValueError('Only exact text prompts are supported')
        self.sequence += 1
        key = f'input-{self.sequence:06d}'
        self.record(key, {'thread_id': self.thread, 'text': prompt})
        try:
            state = StateStore(self.states, self.client.workspace, self.thread).read()
            if state and state.state in (State.ARMED.value, State.EMERGENCY.value):
                rid = self.coordinator.prepare(state, prompt, self.settings)
                self.record(key + '-transaction', {'rollover_id': rid})
                result = self.coordinator.run(rid)
                self.record(key + '-route', result)
                if result['state'] != State.NORMAL.value:
                    raise RuntimeError('Rollover requires recovery: ' + rid)
                self.thread = result['new_thread_id']
                turn = result['accepted_turn_id']
                self.emit({'type': 'rollover', **result})
            elif state and state.state != State.NORMAL.value:
                raise RuntimeError('Source state requires recovery')
            else:
                params = self.settings.turn_params(self.thread, prompt, self.root.name + '-' + key)
                self.record(key + '-intent', params)
                result = self.client.request('turn/start', params)
                turn = result['turn']['id']
                if result['turn']['status'] not in ('inProgress', 'completed'):
                    raise RuntimeError('Turn acceptance unavailable')
                self.record(key + '-accepted', {'thread_id': self.thread, 'turn_id': turn})
            return self.complete(turn, key)
        except BaseException:
            self.blocked = True
            self.emit({'type': 'recovery_required', 'journal': str(self.root), 'automatic_resend': False})
            raise

    def complete(self, turn, key):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            event = self.client.next_event(min(1, max(0, deadline - time.monotonic())))
            if not event:
                continue
            if 'id' in event and 'method' in event:
                if self.approve is None:
                    self.client.respond(event['id'], error={'code': -32601, 'message': 'No approval handler configured'})
                    raise RuntimeError('Runtime requested user input; prompt retained')
                self.client.respond(event['id'], result=self.approve(event))
                continue
            p = event.get('params', {})
            if p.get('threadId') != self.thread:
                continue
            if event.get('method') == 'turn/completed' and p['turn']['id'] == turn:
                self.record(key + '-completed', p)
                if p['turn']['status'] != 'completed':
                    raise RuntimeError('Accepted turn did not complete successfully')
                state = StateStore(self.states, self.client.workspace, self.thread).read()
                if state is None or state.last_turn_id != turn:
                    raise RuntimeError('Native Stop did not persist this turn; check trusted CRG Hooks')
                answer = pending_answer(state).decode('utf-8')
                output = {'type': 'answer', 'thread_id': self.thread, 'turn_id': turn,
                          'text': answer, 'state': state.state,
                          'prediction': state.telemetry.get('guard', {}).get('stop_prediction')}
                self.emit(output)
                return output
        raise TimeoutError('Turn completion timed out; prompt retained, no automatic resend')


def run_chat(args):
    """JSONL interface: prompt text in, answers/approvals/routing events out."""
    import sys
    from .appserver import AppServerClient, ProtocolSchema
    from .config import load_config
    config = load_config(args.workspace)
    if not config.context_rollover.enabled or config.context_rollover.mode != 'MODE_B':
        raise ValueError('Owned chat requires installed MODE_B repo Hooks')
    schema = ProtocolSchema(args.schema)
    client = AppServerClient(schema.runtime_binary, schema, args.workspace,
                             expected_version=schema.runtime_version,
                             command=[schema.runtime_binary, '-c', 'features.hooks=true', 'app-server', '--stdio'])
    def emit(event):
        print(json.dumps(event, ensure_ascii=False), flush=True)
    def approve(event):
        emit({'type': 'approval', 'request': event})
        answer = json.loads(sys.stdin.readline())
        if answer.get('id') != event['id'] or 'result' not in answer:
            raise ValueError('Expected matching approval id and explicit result')
        return answer['result']
    try:
        if args.resume_run and args.reconcile_run:
            raise ValueError("Choose resume or reconcile, not both")
        client.start()
        if args.reconcile_run:
            from .owned_recovery import reconcile_run
            result = reconcile_run(args.reconcile_run, client, config)
            emit(result)
            return 0 if result["state"] == "READY_TO_RESUME" else 1
        listing = client.request('hooks/list', {'cwds': [str(args.workspace.resolve())]})['data'][0]
        # Bind to the installer-owned commands, not merely five arbitrary trusted events.
        receipt_file = args.workspace / 'docs/context-rollover/evidence/mode-b-runtime-review.json'
        expected = json.loads(receipt_file.read_text())['hooks']
        actual = {h['key']: h for h in listing['hooks']}
        if listing.get('errors') or len(expected) != 5 or any(
            h['key'] not in actual or actual[h['key']]['currentHash'] != h['currentHash'] or
            actual[h['key']]['trustStatus'] != 'trusted' or not actual[h['key']]['enabled'] for h in expected):
            raise ValueError('Installed CRG Hook definitions must match reviewed, trusted definitions')
        session = OwnedSession(client, config, timeout=args.timeout, emit=emit, approve=approve)
        params = {'sandbox': 'read-only'}
        if args.permissions:
            params = {'permissions': args.permissions}
        if args.model:
            params['model'] = args.model
        directory = Path(args.resume_run).absolute() if args.resume_run else session.root
        if any(p.is_symlink() for p in [directory, *directory.parents]):
            raise ValueError("Symlink run journal refused")
        if args.resume_run and directory.parent != (session.states / 'owned-runs').resolve():
            raise ValueError('Resume journal must belong to this workspace')
        with exclusive_lock(directory, timeout=.1):
            if args.resume_run:
                session.resume(directory)
            else:
                session.start(params)
            for line in sys.stdin:
                request = json.loads(line)
                if request == {'quit': True}:
                    break
                if not isinstance(request, dict) or set(request) != {'text'}:
                    raise ValueError('Expected a JSON object containing only text, or quit=true')
                session.submit(request['text'])
        return 0
    finally:
        client.close()
