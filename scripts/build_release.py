"""Stdlib-only release builder and verifier. Requires Python 3.11+."""
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python >=3.11 is required")

import argparse
import base64
import csv
import gzip
import tarfile
import re
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
SKILL = 'context-rollover-guard'
ENTRY = b'from crg.cli import main\nraise SystemExit(main())\n'
SHEBANG = b'#!/usr/bin/env python3\n'


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False)+'\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def files(directory):
    result = {}
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Missing or symlink build input directory')
    for path in sorted(directory.rglob('*')):
        relative = path.relative_to(directory)
        if '__pycache__' in relative.parts or path.suffix in {'.pyc', '.pyo'} or path.name == '.DS_Store':
            continue
        if path.is_symlink():
            raise ValueError(f'Symlink build input refused: {path}')
        if path.is_file():
            result[relative.as_posix()] = path.read_bytes()
    return result


def inputs(root):
    result = {'crg/'+name: data for name, data in files(root/'crg').items()}
    # Build metadata belongs only to archives, never the source package.
    if 'crg/_build_info.json' in result:
        raise ValueError('Generated build metadata must not be present in source crg/')
    for name, data in files(root/'skills'/SKILL).items():
        if name not in {'scripts/crg.pyz', 'BUILD-INFO.json'}:
            result[f'skills/{SKILL}/{name}'] = data
    for name in ('pyproject.toml', 'scripts/build_release.py', 'scripts/build_zipapp.py', 'LICENSE', 'README.md', '.codex-plugin/plugin.json'):
        result[name] = (root/name).read_bytes()
    return result


def version(data):
    tree = ast.parse(data.decode())
    values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    if len(values) != 1 or not isinstance(values[0], str):
        raise ValueError('Expected one literal package version')
    return values[0]


def project(source):
    meta = tomllib.loads(source['pyproject.toml'].decode())['project']
    if 'version' in meta or meta.get('dynamic') != ['version']:
        raise ValueError('Package version must use the single dynamic source')
    meta['version'] = version(source['crg/__init__.py'])
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', meta['version']):
        raise ValueError('Unsupported release version')
    if json.loads(source['.codex-plugin/plugin.json'])['version'] != meta['version']:
        raise ValueError('Plugin version disagrees with source version')
    return meta


def archive(entries, *, executable=False):
    stream = io.BytesIO()
    if executable:
        stream.write(SHEBANG)
    # Stored members avoid compressor-version differences; timestamps/modes/order are fixed.
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as output:
        for name, data in sorted(entries.items()):
            member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            output.writestr(member, data)
    return stream.getvalue()


def unpack(data):
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        names = source.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive members')
        if any(Path(name).is_absolute() or '..' in Path(name).parts for name in names):
            raise ValueError('Unsafe archive member')
        return {name: source.read(name) for name in names}


def scan(entries):
    """Reject forbidden state names and common credential/absolute-home signatures.

    This is a deterministic release guard, not a complete secret detector.
    """
    for name, data in entries.items():
        if any(part in {'.codex', '.crg-state', '.env', 'auth.json', 'sessions', 'evidence'} for part in Path(name).parts):
            raise ValueError('Private state in release input')
        if re.search(rb'/(?:Users|home)/[^/\s]+/|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|sk-[A-Za-z0-9_-]{20,}', data):
            raise ValueError('Sensitive signature in release input')


def packages(source, meta, info):
    """PEP 427 pure Python wheel and setuptools-compatible source distribution."""
    name = meta['name'].replace('-', '_') + '-' + meta['version']
    metadata = ('Metadata-Version: 2.1\nName: '+meta['name']+'\nVersion: '+meta['version']+
                '\nSummary: '+meta['description']+'\nRequires-Python: '+meta['requires-python']+
                '\nLicense: Apache-2.0\nLicense-File: LICENSE\nAuthor: FeidaWang\n'+
                'Project-URL: Repository, '+meta['urls']['Repository']+'\n'+
                'Description-Content-Type: text/markdown\n\n').encode()+source['README.md']
    prefix = name+'.dist-info/'
    wheel = {k:v for k,v in source.items() if k.startswith('crg/')}
    wheel.update({'crg/_build_info.json': canonical(info), prefix+'METADATA': metadata,
                  prefix+'LICENSE': source['LICENSE'],
                  prefix+'WHEEL': b'Wheel-Version: 1.0\nGenerator: crg-stdlib-v2\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
                  prefix+'entry_points.txt': b'[console_scripts]\ncrg = crg.cli:main\n'})
    records = io.StringIO(newline='')
    writer = csv.writer(records, lineterminator='\n')
    for k,v in sorted(wheel.items()):
        writer.writerow([k, 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(v).digest()).decode().rstrip('='), str(len(v))])
    writer.writerow([prefix+'RECORD', '', ''])
    wheel[prefix+'RECORD'] = records.getvalue().encode()
    entries = dict(source)
    entries['PKG-INFO'] = metadata
    entries['BUILD-INFO.json'] = canonical(info)
    scan(entries)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for k,v in sorted(entries.items()):
            member = tarfile.TarInfo(name+'/'+k)
            member.size, member.mode, member.mtime = len(v), 0o644, info['epoch']
            tar.addfile(member, io.BytesIO(v))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', mtime=0, compresslevel=9) as gz:
        gz.write(raw.getvalue())
    return {name+'-py3-none-any.whl': archive(wheel), name+'.tar.gz': compressed.getvalue()}


def verify(root, *, dist=None):
    root = Path(root)
    dist = Path(dist) if dist is not None else root/'dist'
    source = inputs(root)
    meta = project(source)
    first = json.loads((dist/'MANIFEST.json').read_bytes())
    second = json.loads((dist/f'{SKILL}.manifest.json').read_bytes())
    if first != second or first.get('format_version') != 1:
        raise ValueError('Release manifests disagree or have unsupported format')
    build = first['build']
    if build['package_version'] != meta['version'] or build['requires_python'] != meta['requires-python']:
        raise ValueError('Release package version/Python compatibility mismatch')
    hashes = {name: digest(data) for name, data in source.items()}
    if hashes != build['source_files'] or digest(canonical(hashes)) != build['source_sha256']:
        raise ValueError('Source snapshot differs from release')
    actual = {name: data for name, data in files(dist).items()
              if name not in {'MANIFEST.json', f'{SKILL}.manifest.json'}}
    for name in packages(source, meta, build):
        actual[name] = (dist/name).read_bytes()
    # Recheck the complete inventory including wheel and sdist.
    if first['artifacts'] != {name: digest(data) for name, data in actual.items()}:
        raise ValueError('Artifact inventory or SHA-256 mismatch')
    for name, data in packages(source, meta, build).items():
        if actual[name] != data:
            raise ValueError('Packaged source/version/metadata mismatch')
    scan(actual)
    pyz = actual['crg.pyz']
    if pyz != actual[f'{SKILL}/scripts/crg.pyz'] or not pyz.startswith(SHEBANG):
        raise ValueError('Runtime copies or portable shebang disagree')
    members = unpack(pyz)
    expected = {name: data for name, data in source.items() if name.startswith('crg/')}
    expected.update({'__main__.py': ENTRY, 'crg/_build_info.json': canonical(build), 'LICENSE': source['LICENSE']})
    if members != expected or version(members['crg/__init__.py']) != build['package_version']:
        raise ValueError('Packaged source/version/build metadata mismatch')
    skill = {name: data for name, data in actual.items() if name.startswith(SKILL+'/')}
    if unpack(actual[f'{SKILL}.zip']) != skill:
        raise ValueError('Skill ZIP differs from installed directory')
    if json.loads(actual[f'{SKILL}/BUILD-INFO.json']) != build:
        raise ValueError('Skill build metadata disagrees')
    for name, data in source.items():
        prefix = 'skills/'+SKILL+'/'
        if name.startswith(prefix) and actual[name.removeprefix('skills/')] != data:
            raise ValueError('Skill source differs from release')
    return {'result': 'PASS', 'package_version': meta['version'], 'source_sha256': build['source_sha256'],
            'artifacts_verified': len(actual), 'source_commit': build['source_commit'],
            'source_dirty': build['source_dirty']}


def build_release(root=ROOT, *, epoch=None, provenance=None):
    root = Path(root).resolve()
    source = inputs(root)
    meta = project(source)
    commit = (provenance['commit'] if provenance is not None else
              subprocess.check_output(['git', 'rev-parse', '--verify', 'HEAD'], cwd=root, text=True).strip())
    if not re.fullmatch(r'[0-9a-f]{40,64}', commit):
        raise ValueError('Invalid source commit provenance')
    status = '' if provenance is not None else subprocess.check_output(['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=root).decode()
    # Restrict dirty provenance to build inputs (generated artifacts are intentionally excluded).
    def is_input(name):
        return (name in source or name.startswith('crg/') or
                name.startswith(f'skills/{SKILL}/') and name not in
                {f'skills/{SKILL}/scripts/crg.pyz', f'skills/{SKILL}/BUILD-INFO.json'})
    dirty = any(is_input(entry[3:]) or is_input(entry) for entry in status.split('\0') if entry)
    if provenance is not None:
        if type(provenance['dirty']) is not bool:
            raise ValueError('Invalid source dirty provenance')
        dirty = provenance['dirty']
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH', '1700000000')) if epoch is None else int(epoch)
    hashes = {name: digest(data) for name, data in source.items()}
    info = {'package_version': meta['version'], 'requires_python': meta['requires-python'],
            'source_commit': commit, 'source_dirty': dirty, 'source_files': hashes,
            'source_sha256': digest(canonical(hashes)),
            'toolchain': {'python': sys.version.split()[0], 'builder': 'stdlib-v2', 'compression': 'stored ZIP; gzip level 9', 'zlib': zlib.ZLIB_RUNTIME_VERSION},
            'epoch': epoch,
            'generated_at': datetime.fromtimestamp(epoch, timezone.utc).isoformat()}
    runtime = {name: data for name, data in source.items() if name.startswith('crg/')}
    runtime.update({'__main__.py': ENTRY, 'crg/_build_info.json': canonical(info), 'LICENSE': source['LICENSE']})
    pyz = archive(runtime, executable=True)
    skill = {name.removeprefix('skills/'): data for name, data in source.items() if name.startswith(f'skills/{SKILL}/')}
    skill[f'{SKILL}/scripts/crg.pyz'] = pyz
    skill[f'{SKILL}/BUILD-INFO.json'] = canonical(info)
    skill[f'{SKILL}/LICENSE'] = source['LICENSE']
    outputs = {'crg.pyz': pyz, **skill, f'{SKILL}.zip': archive(skill)}
    outputs.update(packages(source, meta, info))
    scan(outputs)
    manifest = canonical({'format_version': 1, 'build': info,
                          'artifacts': {name: digest(data) for name, data in outputs.items()}})
    outputs['MANIFEST.json'] = manifest
    outputs[f'{SKILL}.manifest.json'] = manifest
    # Stage and verify everything before publishing any output. Manifests are published last.
    with tempfile.TemporaryDirectory(prefix='crg-release-') as tmp:
        stage = Path(tmp)
        for name, data in outputs.items():
            target = stage/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        verify(root, dist=stage)
        if inputs(root) != source:
            raise ValueError('Build inputs changed; retry explicitly with a stable source snapshot')
        for name, data in outputs.items():
            target = root/'dist'/name
            if any(path.is_symlink() for path in [target, *target.parents]):
                raise ValueError('Symlink output refused')
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, pending = tempfile.mkstemp(prefix='.release-', dir=target.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(pending, 0o755 if name.endswith('.pyz') else 0o644)
                os.replace(pending, target)
            finally:
                if os.path.exists(pending): os.unlink(pending)
    return verify(root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='Read-only source/artifact/version verification')
    args = parser.parse_args(argv)
    try:
        result = verify(ROOT) if args.verify else build_release(ROOT)
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(json.dumps({'result': 'FAIL', 'error': str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
