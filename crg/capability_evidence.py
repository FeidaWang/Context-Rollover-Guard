"""Atomic capability generations; cached observations never grant session authority."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

MAX_ACTION_AGE_SECONDS = 86400


def digest(data):
    return hashlib.sha256(data).hexdigest()


def binding_digest(manifest):
    fields = ('generation', 'binary', 'binary_sha256', 'codex_version', 'surface',
              'checked_at', 'schema_root', 'schema_sha256')
    return digest(json.dumps({k: manifest[k] for k in fields}, sort_keys=True,
                             separators=(',', ':')).encode())


def publish(receipt, schema_root, result, documents):
    """Write immutable generation first, then atomically publish its complete pointer."""
    from .capability_probe import _write_private
    for name in documents:
        if not isinstance(name, str) or not name.endswith('.json') or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Invalid schema document path')
    manifest = dict(result)
    manifest.update(evidence_version=1, generation=uuid.uuid4().hex,
                    checked_at=datetime.now(timezone.utc).isoformat(),
                    schema_root=str(schema_root.resolve()),
                    schema_sha256={name: digest(data) for name, data in documents.items()})
    for name, data in documents.items():
        _write_private(schema_root / manifest['generation'] / name, data)
    manifest['binding_sha256'] = binding_digest(manifest)
    _write_private(receipt, (json.dumps(manifest, indent=2) + '\n').encode())
    return manifest


def validate(manifest, schema_root, *, binary=None, surface=None, for_action=False):
    """Return a verified generation path; raises on unknown/legacy evidence."""
    if not isinstance(manifest, dict) or manifest.get('evidence_version') != 1:
        raise ValueError('Current capability manifest required')
    try:
        if binding_digest(manifest) != manifest['binding_sha256']:
            raise ValueError('Capability generation binding mismatch')
        generation = manifest['generation']
        if len(generation) != 32 or any(c not in '0123456789abcdef' for c in generation):
            raise ValueError('Invalid capability generation')
        if Path(manifest['schema_root']) != schema_root.resolve():
            raise ValueError('Capability installation path mismatch')
        checked = datetime.fromisoformat(manifest['checked_at'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        if age < 0 or for_action and age > MAX_ACTION_AGE_SECONDS:
            raise ValueError('Capability evidence is stale for action')
        for key in ('binary', 'binary_sha256', 'codex_version', 'surface'):
            if not isinstance(manifest[key], str) or not manifest[key]:
                raise ValueError('Incomplete runtime binding')
        if surface is not None and surface != manifest['surface']:
            raise ValueError('Capability surface mismatch')
        if binary is not None:
            if (Path(binary).resolve() != Path(manifest['binary']).resolve() or
                    digest(Path(binary).read_bytes()) != manifest['binary_sha256']):
                raise ValueError('Runtime executable changed')
        hashes = manifest['schema_sha256']
        if not isinstance(hashes, dict) or 'ClientRequest.json' not in hashes:
            raise ValueError('Incomplete capability schema')
        root = schema_root / generation
        if root.is_symlink():
            raise ValueError('Symlink capability generation')
        if {str(p.relative_to(root)) for p in root.rglob('*.json')} != set(hashes):
            raise ValueError('Mixed or incomplete capability generation')
        for name, expected in hashes.items():
            path = root / name
            if (Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink()
                    or not path.resolve().is_relative_to(root.resolve())
                    or digest(path.read_bytes()) != expected):
                raise ValueError('Capability schema integrity mismatch')
        if manifest.get('errors') or manifest.get('schema_generation_ok') is not True:
            raise ValueError('Incomplete capability probe')
        return root
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Malformed capability manifest') from exc
