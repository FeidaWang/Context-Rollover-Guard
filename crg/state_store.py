"""POSIX local-filesystem store: locked read-modify-write, checksums and backup.

A recovery from backup is never returned as actionable old state. Unknown future
schemas fail closed. No automatic transaction replay or prompt forwarding exists.
"""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import copy
import fcntl
import hashlib
import json
import os
import stat
import tempfile
import time
import uuid
from .domain import SessionState, State, now, workspace_id
from .durable import read_private, open_private_lock


class StoreError(RuntimeError):
    pass


class CorruptState(StoreError):
    pass


class FutureSchema(StoreError):
    pass


class RecoveryRequired(StoreError):
    pass


class Conflict(StoreError):
    pass


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def decode(raw: bytes) -> SessionState:
    try:
        outer = json.loads(raw, object_pairs_hook=_pairs)
        if not isinstance(outer, dict):
            raise ValueError("Invalid envelope")
        # Only CRG's documented v0 plain-state format is accepted for migration.
        if "payload" in outer:
            if type(outer.get("format_version")) is not int or outer.get("format_version") != 1:
                raise FutureSchema("Unsupported envelope version; do not downgrade")
            payload = outer["payload"]
            if outer.get("sha256") != hashlib.sha256(canonical(payload)).hexdigest():
                raise ValueError("Checksum mismatch")
        elif outer.get("schema_version") == 0:
            payload = outer
        else:
            raise ValueError("Missing integrity envelope")
        version = payload.get("schema_version")
        if type(version) is not int or version < 0:
            raise ValueError("Invalid schema version")
        if version > 1:
            raise FutureSchema("Future state schema; do not downgrade")
        payload = dict(payload)
        if version == 0:
            payload.update(schema_version=1, state=State.RECOVERY.value,
                           recovery_reason="MIGRATED_V0_REQUIRES_RECONCILIATION")
            payload.setdefault("revision", 0)
            payload.setdefault("updated_at", now())
        return SessionState(**payload).validate()
    except FutureSchema:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError) as exc:
        raise CorruptState("Invalid CRG state; original file retained") from exc


def encode(state: SessionState) -> bytes:
    payload = state.to_dict()
    return canonical({"format_version": 1, "payload": payload,
                      "sha256": hashlib.sha256(canonical(payload)).hexdigest()})


def _directory(path: Path):
    """Create private CRG directories, rejecting symlinks and foreign ownership."""
    if path.is_symlink():
        raise StoreError("Symlink directory refused")
    path.mkdir(mode=0o700, exist_ok=True)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise StoreError("State directory must be owned by current user with mode 0700")


class StateStore:
    def __init__(self, root: Path, cwd: Path, session_id: str, *, timeout: float = 10,
                 fault=None):
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id required")
        if timeout < 0:
            raise ValueError("Invalid timeout")
        self.cwd = cwd.resolve()
        self.session_id = session_id
        self.timeout = timeout
        self.fault = fault or (lambda stage: None)
        # Caller must supply an existing parent; do not chmod users' directories.
        root = root.expanduser().absolute()
        if any(p.is_symlink() for p in [root, *root.parents]):
            raise StoreError("Symlink state root refused")
        session_key = hashlib.sha256(session_id.encode()).hexdigest()
        current = root
        for part in (None, "workspaces", workspace_id(self.cwd), "sessions", session_key):
            if part is not None:
                current /= part
            _directory(current)
        self.directory = current
        self.path = current / "state.json"
        self.backup = current / "state.backup.json"

    @contextmanager
    def _lock(self):
        fd = open_private_lock(self.directory / "state.lock")
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("CRG state lock timed out")
                    time.sleep(0.01)
            yield
        finally:
            os.close(fd)

    def _read_bytes(self, path: Path):
        try:
            return read_private(path,max_bytes=16*1024*1024)
        except FileNotFoundError:
            return None
        except ValueError as exc:
            raise StoreError('Unsafe or oversized state file') from exc

    def _decode(self, raw):
        state = decode(raw)
        if (state.cwd != str(self.cwd) or state.workspace_id != workspace_id(self.cwd)
                or state.session_id != self.session_id):
            raise CorruptState("State belongs to another workspace/session")
        return state

    def _load(self):
        raw = self._read_bytes(self.path)
        if raw is not None:
            try:
                return self._decode(raw), False
            except CorruptState:
                pass
        backup = self._read_bytes(self.backup)
        if backup is not None:
            try:
                state = self._decode(backup)
            except CorruptState:
                raise CorruptState("Primary and backup unusable; retained for inspection")
            return replace(state, state=State.RECOVERY.value,
                           recovery_reason="PRIMARY_MISSING_OR_CORRUPT", updated_at=now()), True
        if raw is not None or any(self.directory.glob(".*.tmp")):
            raise CorruptState("No complete state available; explicit recovery required")
        return None, False

    def read(self):
        with self._lock():
            state, _ = self._load()
            return state

    def _atomic(self, path: Path, data: bytes, label: str):
        fd, temp = tempfile.mkstemp(prefix=f".{label}.", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data[:len(data)//2])
                f.flush()
                self.fault(f"{label}:partial")
                f.write(data[len(data)//2:])
                f.flush()
                os.fsync(f.fileno())
                self.fault(f"{label}:fsync")
            os.replace(temp, path)
            self.fault(f"{label}:rename")
            dfd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
            self.fault(f"{label}:dirsync")
        finally:
            if os.path.exists(temp):
                os.unlink(temp)  # only our own incomplete temporary file

    def update(self, mutate, *, initial: SessionState | None = None,
               expected_revision: int | None = None, evidence: dict | None = None):
        with self._lock():
            old, fallback = self._load()
            if fallback:
                raise RecoveryRequired("Repair backup recovery before mutation")
            if old is not None and old.state == State.RECOVERY.value:
                raise RecoveryRequired("Reconcile state before any business mutation")
            if old is None:
                if initial is None:
                    raise StoreError("No session state; initial required")
                base = initial.validate()
            else:
                base = old
            if expected_revision is not None and base.revision != expected_revision:
                raise Conflict("Stale state revision")
            candidate = mutate(copy.deepcopy(base))
            if not isinstance(candidate, SessionState):
                raise ValueError("Mutation must return SessionState")
            candidate.validate()
            if any(getattr(candidate, k) != getattr(base, k) for k in
                   ("workspace_id", "cwd", "session_id", "thread_id", "revision")):
                raise ValueError("Mutation changed immutable identity or revision")
            self._decode(encode(candidate))
            if candidate.state != base.state:
                base.transition(State(candidate.state), evidence=evidence)
            if old is not None and candidate == old:
                return old
            candidate = replace(candidate, revision=base.revision + 1, updated_at=now())
            data = encode(candidate)
            # First write also makes a full durable backup before installing primary.
            self._atomic(self.backup, encode(old) if old is not None else data, "backup")
            self._atomic(self.path, data, "primary")
            return candidate

    def repair(self):
        """Restore readable bytes only, preserving damage and requiring reconciliation."""
        with self._lock():
            state, fallback = self._load()
            if state is None:
                raise StoreError("Nothing to repair")
            raw = self._read_bytes(self.path)
            legacy = raw is not None and json.loads(raw).get("schema_version") == 0 if not fallback else False
            if not fallback and not legacy:
                return state
            if raw is not None:
                self._atomic(self.directory / f"state.corrupt.{uuid.uuid4().hex}.json", raw, "quarantine")
            recovered = replace(state, revision=state.revision + 1, updated_at=now())
            self._atomic(self.path, encode(recovered), "repair")
            return recovered
