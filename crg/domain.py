"""Versioned session state and explicit legal transitions; no runtime actions."""
from dataclasses import dataclass, field, asdict, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import hashlib
import math


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def workspace_id(cwd: str | Path) -> str:
    return hashlib.sha256(str(Path(cwd).resolve()).encode()).hexdigest()


class Mode(str, Enum):
    A = "MODE_A"
    B = "MODE_B"
    C = "MODE_C"


class State(str, Enum):
    NORMAL = "NORMAL"
    ARMED = "ARMED"
    PREPARING = "ROLLOVER_PREPARING"
    STARTING = "ROLLOVER_STARTING_THREAD"
    FORWARDING = "ROLLOVER_FORWARDING"
    ARCHIVING = "ROLLOVER_ARCHIVING"
    EMERGENCY = "EMERGENCY"
    RECOVERY = "RECOVERY_REQUIRED"


EDGES = {
    State.NORMAL: {State.ARMED, State.EMERGENCY},
    State.ARMED: {State.PREPARING, State.EMERGENCY},
    State.EMERGENCY: {State.PREPARING},
    State.PREPARING: {State.STARTING},
    State.STARTING: {State.FORWARDING},
    State.FORWARDING: {State.ARCHIVING},
    State.ARCHIVING: {State.NORMAL},
    State.RECOVERY: set(),
}


@dataclass(frozen=True)
class SessionState:
    workspace_id: str
    session_id: str
    thread_id: str
    cwd: str
    schema_version: int = 1
    state: str = State.NORMAL.value
    mode: str = Mode.A.value
    revision: int = 0
    updated_at: str = field(default_factory=now)
    last_turn_id: str | None = None
    model: str | None = None
    last_active_context_tokens: int | None = None
    model_context_window: int | None = None
    effective_auto_compact_limit: int | None = None
    predicted_next_growth: int | None = None
    safety_buffer: int | None = None
    risk_score: float | None = None
    threshold_source: str | None = None
    pending_answer_path: str | None = None
    rollover_id: str | None = None
    recovery_reason: str | None = None
    telemetry: dict = field(default_factory=dict)

    @classmethod
    def create(cls, cwd: Path, session_id: str, thread_id: str):
        return cls(workspace_id(cwd), session_id, thread_id, str(cwd.resolve()))

    def validate(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported state schema")
        State(self.state)
        Mode(self.mode)
        if not isinstance(self.cwd, str) or not Path(self.cwd).is_absolute():
            raise ValueError("cwd must be absolute")
        if self.workspace_id != workspace_id(self.cwd):
            raise ValueError("workspace identity mismatch")
        for key in ("session_id", "thread_id", "updated_at"):
            if not isinstance(getattr(self, key), str) or not getattr(self, key):
                raise ValueError(f"Invalid {key}")
        if datetime.fromisoformat(self.updated_at).tzinfo is None:
            raise ValueError("Timestamp must have timezone")
        for key in ("revision", "last_active_context_tokens", "model_context_window",
                    "effective_auto_compact_limit", "predicted_next_growth", "safety_buffer"):
            v = getattr(self, key)
            if v is not None and (type(v) is not int or v < 0):
                raise ValueError(f"Invalid {key}")
        if self.revision is None:
            raise ValueError("Missing revision")
        if self.risk_score is not None and (type(self.risk_score) not in (int, float)
                or not math.isfinite(self.risk_score) or not 0 <= self.risk_score <= 1):
            raise ValueError("Invalid risk")
        for key in ("last_turn_id", "model", "threshold_source", "pending_answer_path",
                    "rollover_id", "recovery_reason"):
            if getattr(self, key) is not None and not isinstance(getattr(self, key), str):
                raise ValueError(f"Invalid {key}")
        if not isinstance(self.telemetry, dict):
            raise ValueError("Invalid telemetry")
        return self

    def to_dict(self):
        self.validate()
        return asdict(self)

    def transition(self, target: State, *, evidence: dict | None = None):
        self.validate()
        target = State(target)
        current = State(self.state)
        if target == current:
            return self
        if target != State.RECOVERY and target not in EDGES[current]:
            raise ValueError(f"Illegal transition: {current.value} -> {target.value}")
        required = {
            State.PREPARING: ("prompt_persisted",),
            State.STARTING: ("prompt_persisted", "answer_archived", "handoff_written"),
            State.FORWARDING: ("new_thread_started",),
            State.ARCHIVING: ("turn_accepted",),
            State.NORMAL: ("transaction_committed",),
        }
        if any((evidence or {}).get(k) is not True for k in required.get(target, ())):
            raise ValueError("Missing durable transaction evidence")
        return replace(self, state=target.value, updated_at=now())
