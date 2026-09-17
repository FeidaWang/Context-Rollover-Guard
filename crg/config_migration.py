"""Preview an additive workspace migration; explicit apply creates a new candidate."""
import hashlib
from pathlib import Path
import tomllib

from .config import resolve_config, migration_diagnostics
from .durable import immutable_write


def migrate(workspace, *, apply=False, output=None, expected_sha256=None):
    workspace = Path(workspace).resolve()
    source = workspace / 'crg.toml'
    if source.is_symlink() or not source.is_file():
        raise ValueError('Migration requires a regular workspace crg.toml')
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if expected_sha256 is not None and expected_sha256 != digest:
        raise ValueError('Configuration changed since preview')
    document = tomllib.loads(original.decode('utf-8'))
    # Validate this file independently; never copy user-level settings or secrets.
    config, sources = resolve_config(workspace, user_file=source, repo_file=source)
    candidate = original
    if 'continuity' not in document:
        candidate += b'\n[continuity]\npolicy = "native_cooperative"\n'
    elif 'policy' not in document['continuity']:
        # Do not guess where a TOML table ends or rewrite user comments.
        raise ValueError('Existing continuity table has no policy; add it explicitly before migration')
    result = dict(dry_run=not apply, source_sha256=digest,
                  candidate_sha256=hashlib.sha256(candidate).hexdigest(),
                  candidate=candidate.decode('utf-8'), diagnostics=migration_diagnostics(config, sources),
                  original_preserved=True, recovery_state_modified=False, hooks_installed=False)
    if apply:
        if output is None or expected_sha256 is None:
            raise ValueError('Apply requires --output and --expected-sha256 from the preview')
        output = Path(output)
        if not output.is_absolute():
            output = workspace / output
        # Only a new direct-child TOML candidate; no state paths or config replacement.
        if output.parent.resolve() != workspace or output.suffix != '.toml' or output.name == 'crg.toml':
            raise ValueError('Output must be a new workspace TOML candidate, not crg.toml')
        if output.exists() or output.is_symlink():
            raise ValueError('Migration never overwrites an existing destination')
        if source.read_bytes() != original:
            raise ValueError('Configuration changed during migration')
        immutable_write(output, candidate)
        result['created'] = str(output)
    return result
