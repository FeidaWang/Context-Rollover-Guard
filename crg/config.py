"""CRG-only configuration; never writes Codex configuration."""
from dataclasses import dataclass, field, fields
from pathlib import Path
import math
import os
import tomllib


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class General:
    enabled: bool = False
    mode: str = "auto"
    codex_binary: str = ""  # explicitly selected runtime; empty uses PATH
    archive_root: str = ".codex/context-archive"
    state_root: str = ""  # resolved from CODEX_HOME, not created while loading
    schema_cache: str = ""
    capability_receipt: str = ""
    hook_receipts: str = ""
    evidence_exports: str = ""


@dataclass(frozen=True)
class Predictor:
    window_size: int = 8
    min_growth_tokens: int = 8000
    safety_buffer_tokens: int = 8000
    safety_buffer_percent: float = 0.03
    warn_probability: float = 0.75  # reserved; v1 ratio is not a probability
    hard_arm_remaining_tokens: int = 12000
    derived_limit_percent: float = 0.90
    conservative_limit_percent: float = 0.80


@dataclass(frozen=True)
class Rollover:
    archive_old_thread: bool = True
    preserve_model: bool = True
    preserve_cwd: bool = True
    preserve_permissions: bool = True
    forward_original_prompt: bool = True


@dataclass(frozen=True)
class Emergency:
    block_auto_compact: bool = False
    force_rollover_on_next_prompt: bool = False


@dataclass(frozen=True)
class Config:
    context_rollover: General = field(default_factory=General)
    predictor: Predictor = field(default_factory=Predictor)
    rollover: Rollover = field(default_factory=Rollover)
    emergency: Emergency = field(default_factory=Emergency)

    def paths(self, workspace: Path) -> tuple[Path, Path]:
        from .runtime_paths import RuntimePaths
        paths = RuntimePaths.resolve(workspace, self)
        return paths.archive_root, paths.state_root



SECTIONS = {"context_rollover": General, "predictor": Predictor,
            "rollover": Rollover, "emergency": Emergency}


def load_config(workspace: Path, user_file: Path | None = None,
                repo_file: Path | None = None, overrides: dict | None = None) -> Config:
    return resolve_config(workspace, user_file, repo_file, overrides)[0]


def resolve_config(workspace: Path, user_file: Path | None = None,
                   repo_file: Path | None = None, overrides: dict | None = None):
    """Return validated config and per-field provenance without writes or runtime calls."""
    provenance = {name: {f.name: "default" for f in fields(cls)}
                  for name, cls in SECTIONS.items()}
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    merged = {name: {} for name in SECTIONS}
    merged["context_rollover"]["state_root"] = str(home / "context-rollover")
    sources = []
    for label, path in zip(("user", "repo"), (user_file if user_file is not None else home / "context-rollover.toml",
                 repo_file if repo_file is not None else workspace / "crg.toml")):
        if path.exists():
            try:
                with path.open("rb") as f:
                    sources.append((label, tomllib.load(f)))
            except (OSError, tomllib.TOMLDecodeError) as exc:
                raise ConfigurationError(f"Invalid CRG configuration: {path}") from exc
    sources.append(("cli", overrides or {}))
    for label, source in sources:
        if not isinstance(source, dict) or set(source) - set(SECTIONS):
            raise ConfigurationError("Unknown CRG configuration section")
        for name, values in source.items():
            if not isinstance(values, dict) or set(values) - {f.name for f in fields(SECTIONS[name])}:
                raise ConfigurationError(f"Unknown field or invalid section: {name}")
            merged[name].update(values)
            provenance[name].update({key: label for key in values})
    objects = {}
    for name, cls in SECTIONS.items():
        defaults = cls()
        for key, value in merged[name].items():
            expected = type(getattr(defaults, key))
            valid = type(value) is expected
            if expected is float:
                valid = type(value) in (int, float) and math.isfinite(value)
            if not valid:
                raise ConfigurationError(f"Invalid type: {name}.{key}")
        objects[name] = cls(**merged[name])
    c = Config(**objects)
    if c.context_rollover.mode not in {"auto", "MODE_A", "MODE_B", "MODE_C"}:
        raise ConfigurationError("Invalid mode")
    if not c.context_rollover.archive_root or not c.context_rollover.state_root:
        raise ConfigurationError("Storage paths must not be empty")
    for f in fields(Predictor):
        v = getattr(c.predictor, f.name)
        if f.name == "window_size" and not 1 <= v <= 10000:
            raise ConfigurationError("window_size outside 1..10000")
        if f.name.endswith("tokens") and v < 0:
            raise ConfigurationError(f"Negative {f.name}")
        if ("percent" in f.name or f.name == "warn_probability") and not 0 <= v <= 1:
            raise ConfigurationError(f"Invalid fraction: {f.name}")
    if not 0 < c.predictor.conservative_limit_percent <= c.predictor.derived_limit_percent <= 1:
        raise ConfigurationError("Invalid compact limit fractions")
    if not all((c.rollover.preserve_cwd, c.rollover.preserve_permissions,
                c.rollover.forward_original_prompt)):
        raise ConfigurationError("CRG invariants cannot be disabled")
    return c, provenance
