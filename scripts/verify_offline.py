"""Verify an allowlisted disposable snapshot; no credentials or Git commits.

--network-policy=os requires an OS boundary and verifies it before running tests.
The local audit mode cannot certify OS isolation. No live runners are executed.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

if sys.version_info < (3, 11):
    raise SystemExit('Python >=3.11 is required')
ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ('crg/', 'scripts/', 'tests/', 'skills/', '.github/workflows/')
SINGLES = {'README.md', 'README.zh-CN.md', 'LICENSE', 'pyproject.toml', 'crg.toml', '.codex-plugin/plugin.json', '.gitignore'}


def selected(name):
    path = Path(name)
    return (not path.is_absolute() and '..' not in path.parts and
            (name in SINGLES or name.startswith(PREFIXES)) and
            not any(p in {'.env', 'auth.json', '__pycache__', '.crg-state', '.codex'} for p in path.parts) and
            path.suffix not in {'.pyc', '.pyo'})


def environment(root, checkout):
    """Never inherit ambient credentials, proxies, Python startup paths or hooks."""
    for name in ('home', 'codex', 'bin'):
        (root/name).mkdir()
    (root/'bin/python3').symlink_to(sys.executable)
    (root/'bin/git').symlink_to(shutil.which('git'))
    return dict(PATH=str(root/'bin'), HOME=str(root/'home'), CODEX_HOME=str(root/'codex'),
                PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
                PYTHONPATH=str(checkout/'tests/support/offline_guard')+os.pathsep+str(checkout),
                SOURCE_DATE_EPOCH='1700000000', LC_ALL='C')


def assert_os_network(env, cwd):
    # -I ignores the Python audit hook: a successful guard here must come from OS.
    # Linux's empty network namespace must have no route; macOS must deny bind.
    code = '''import errno, socket, sys
from pathlib import Path
if sys.platform.startswith('linux'):
    # Query the current network namespace, not an inherited sysfs mount.
    if sorted(name for _, name in socket.if_nameindex()) != ['lo']:
        raise RuntimeError('Expected isolated namespace with loopback only')
    if len(Path('/proc/net/route').read_text().splitlines()) != 1:
        raise RuntimeError('Unexpected route in isolated namespace')
s = socket.socket()
s.settimeout(1)
try:
    if sys.platform == 'darwin': s.bind(('127.0.0.1', 0))
    elif sys.platform.startswith('linux'): s.connect(('192.0.2.1', 9))
    else: raise RuntimeError('Unsupported OS network verification')
except OSError as e:
    allowed = {errno.EPERM, errno.EACCES} if sys.platform == 'darwin' else {errno.ENETUNREACH, errno.EPERM, errno.EACCES}
    if e.errno not in allowed: raise
else: raise RuntimeError('OS network boundary absent')
finally: s.close()
'''
    subprocess.run([sys.executable, '-I', '-c', code], cwd=cwd, env=env, check=True, timeout=5)


def run(args, cwd, env):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=240)
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, args)
    return result.stdout + result.stderr


def verify(source=ROOT, *, network_policy='audit'):
    source = Path(source).resolve()
    # Read provenance only; never copy .git, account files, ignored evidence or a remote URL.
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', 'HEAD'], cwd=source, text=True).strip()
    status = subprocess.check_output(['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=source)
    names = subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'], cwd=source).decode().split('\0')
    names = sorted({n for n in names if selected(n)})
    checks = []
    with tempfile.TemporaryDirectory(prefix='crg-offline-') as temp:
        root = Path(temp).resolve()
        checkout = root/'checkout'; checkout.mkdir()
        for name in names:
            origin, target = source/name, checkout/name
            if not origin.exists():
                continue  # deleted tracked paths must remain absent
            if any(p.is_symlink() for p in [origin, *origin.parents]):
                raise RuntimeError('Refusing symlink snapshot input: '+name)
            if not origin.is_file():
                raise RuntimeError('Refusing non-file snapshot input: '+name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, target)
        env = environment(root, checkout)
        if network_policy == 'os': assert_os_network(env, checkout)
        # Empty repository is only for workspace detection; no add/commit or user config.
        subprocess.run([str(root/'bin/git'), 'init', '-q', str(checkout)], env=env, check=True)
        # Build inside the disposable source with explicitly captured Git provenance.
        script = "import json, sys; sys.path.insert(0, 'scripts'); from build_release import build_release; print(json.dumps(build_release('.', provenance=json.loads(sys.argv[1]))))"
        provenance = json.dumps({'commit':commit, 'dirty':bool(status)})
        run([sys.executable,'-c',script,provenance], checkout, env)
        for suite in ('unit','integration'):
            command = [sys.executable, '-m','unittest','discover','-s','tests/'+suite,'-v']
            output = run(command, checkout, env)
            count = re.search(r'Ran (\d+) tests?', output)
            if not count or int(count[1]) == 0 or re.search(r'skipped=\d+', output):
                raise RuntimeError('Required suite empty or skipped')
            checks.append({'suite':suite,'passed':int(count[1]),'failed':0,'skipped':0})
        run([sys.executable,'scripts/build_release.py','--verify'], checkout, env)
        run([sys.executable,'scripts/check_release.py'], checkout, env)
    result = {'result':'PASS', 'python':sys.version.split()[0], 'source_commit':commit,
              'source_dirty':bool(status), 'network_policy':network_policy,
              'os_network_verified':network_policy=='os', 'checks':checks,
              'artifacts':'build + verify + 3 out-of-tree smoke checks',
              'hosted_ci':'NOT_RUN by this local invocation'}
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clean', action='store_true', help='Compatibility flag; all runs use disposable snapshots')
    parser.add_argument('--network-policy', choices=('audit','os'), default='audit')
    parser.add_argument('--report', type=Path, help='Save content-free result JSON locally')
    args = parser.parse_args()
    result = verify(network_policy=args.network_policy)
    if args.report:
        args.report.write_text(json.dumps(result,indent=2)+'\n')

if __name__ == '__main__':
    main()
