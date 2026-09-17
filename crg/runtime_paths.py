"""Resolve runtime storage without creating files or relying on a source checkout."""
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class RuntimePaths:
    state_root: Path
    archive_root: Path
    schema_cache: Path
    capability_receipt: Path
    hook_receipts: Path
    evidence_exports: Path | None

    @classmethod
    def resolve(cls, workspace, config, *, evidence=None):
        workspace = Path(workspace).resolve()
        def path(value):
            return (workspace / Path(value).expanduser()).absolute()
        general = config.context_rollover
        home = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
        state = path(general.state_root or home/'context-rollover')
        runtime = path(evidence) if evidence is not None else path(general.evidence_root or state/'runtime')
        return cls(state, path(general.archive_root),
                   runtime/'schema' if evidence is not None else path(general.schema_cache or runtime/'schema'),
                   runtime/'capabilities.json' if evidence is not None else path(general.capability_receipt or runtime/'capabilities.json'),
                   path(general.hook_receipts or state/'hooks'),
                   path(general.evidence_exports) if general.evidence_exports else None)

    @property
    def hook_review(self):
        return self.hook_receipts/'mode-b-runtime-review.json'

    def as_dict(self):
        return {key: str(value) if value is not None else None for key, value in vars(self).items()}
