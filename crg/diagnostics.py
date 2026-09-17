"""Read-only diagnostics. Cached observations never prove live session activation."""
import hashlib
import json
from pathlib import Path
import shutil
from .runtime_paths import RuntimePaths


def diagnose(workspace, config, sources, *, evidence=None, binary=None):
    paths = RuntimePaths.resolve(workspace, config, evidence=evidence)
    errors = []
    def read(path):
        try:
            value = json.loads(path.read_text())
            if not isinstance(value, dict):
                raise ValueError('Expected object')
            return value
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            errors.append(f'Invalid or unreadable metadata: {path}')
            return {}
    receipt = read(paths.capability_receipt)
    executable = shutil.which(binary or config.context_rollover.codex_binary or 'codex')
    verified = False
    try:
        hashes = receipt.get('schema_sha256', {})
        if (executable and receipt.get('binary') and receipt.get('schema_generation_ok') is True
                and isinstance(receipt.get('codex_version'), str) and receipt['codex_version']
                and Path(executable).resolve() == Path(receipt['binary']).resolve()
                and isinstance(hashes, dict) and 'ClientRequest.json' in hashes):
            for name, digest in hashes.items():
                target = paths.schema_cache/name
                if Path(name).is_absolute() or not target.resolve().is_relative_to(paths.schema_cache.resolve()):
                    raise ValueError('Invalid schema path')
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ValueError('Schema integrity mismatch')
            from .appserver import ProtocolSchema
            schema = ProtocolSchema(paths.schema_cache, manifest_path=paths.capability_receipt)
            if not {'initialize', 'thread/start', 'turn/start', 'thread/archive'} <= set(schema.methods):
                raise ValueError('Required request definitions missing')
            verified = True
    except (OSError, ValueError, TypeError, RuntimeError, KeyError, AttributeError):
        errors.append('Schema cache is incomplete, corrupt, or unbound')
    hooks = read(Path(workspace)/'.codex/hooks.json').get('hooks', {})
    discovered = isinstance(hooks, dict) and any(isinstance(v, list) and bool(v) for v in hooks.values())
    warnings = []
    if config.context_rollover.mode != 'auto':
        warnings.append('Legacy MODE_A/B/C policy names remain supported; migration tooling is pending.')
    return {
        'configured': any(source != 'default' for section in sources.values() for source in section.values()),
        'runtime_available': executable is not None,
        'schema_verified': verified,
        'hooks_discovered': discovered,
        'hooks_trusted': None,
        'telemetry_available': None,
        'guard_enabled': config.context_rollover.enabled,
        'guard_active_for_session': None if config.context_rollover.enabled else False,
        'paths': paths.as_dict(),
        'configured_mode': config.context_rollover.mode,
        'runtime_binary': executable,
        'cached_runtime_version': receipt.get('codex_version'),
        'observed_at': receipt.get('generated_at'),
        'cached_probe_errors': receipt.get('errors', []) if isinstance(receipt.get('errors', []), list) else ['Invalid cached error list'],
        'evidence_kind': 'cached integrity only; current runtime version and session activation unverified',
        'hooks_scope': 'workspace hook definitions; presence does not establish CRG ownership or trust',
        'warnings': warnings,
        'errors': errors,
    }


def render_human(result):
    fields = ('configured', 'runtime_available', 'schema_verified', 'hooks_discovered',
              'hooks_trusted', 'telemetry_available', 'guard_enabled', 'guard_active_for_session')
    def label(value):
        return 'UNKNOWN' if value is None else 'yes' if value else 'no'
    lines = [f'{key}: {label(result[key])}' for key in fields]
    lines.append('Evidence: '+result['evidence_kind'])
    lines.extend('Warning: '+text for text in result['warnings'])
    lines.extend('Error: '+text for text in result['errors'])
    lines.extend('Cached probe error: '+str(text) for text in result['cached_probe_errors'])
    return '\n'.join(lines)


def initialize(workspace):
    """Explicit local config creation only; never overwrite or install hooks."""
    from .durable import immutable_write
    workspace = Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError('Workspace must already exist')
    path = workspace/'crg.toml'
    if path.exists() or path.is_symlink():
        raise ValueError('crg.toml already exists; initialization never overwrites configuration')
    content = b'[context_rollover]\nenabled = false\nmode = "auto"\n\n[emergency]\nblock_auto_compact = false\nforce_rollover_on_next_prompt = false\n'
    immutable_write(path, content)
    return {'created': str(path), 'guard_enabled': False, 'hooks_installed': False}
