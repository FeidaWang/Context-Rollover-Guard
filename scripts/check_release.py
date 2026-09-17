"""Offline smoke tests of final artifacts outside the checkout (Python >=3.11)."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import zipfile


def check(dist):
    dist = Path(dist).resolve()
    with tempfile.TemporaryDirectory(prefix='crg-artifact-check-') as temp:
        root = Path(temp)
        env = {k:v for k,v in os.environ.items() if k in {'PATH', 'SYSTEMROOT', 'TMPDIR'}}
        env.update(HOME=str(root/'home'), CODEX_HOME=str(root/'codex'), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
        guard = Path(__file__).resolve().parents[1]/'tests/support/offline_guard'
        if guard.is_dir(): env['PYTHONPATH'] = str(guard)
        for name in ('home','codex'): (root/name).mkdir()
        with zipfile.ZipFile(dist/'context-rollover-guard.zip') as bundle:
            bundle.extractall(root/'skill')
        with zipfile.ZipFile(next(dist.glob('*.whl'))) as bundle:
            bundle.extractall(root/'wheel')
        commands = [
            [sys.executable, str(root/'skill/context-rollover-guard/scripts/self_test.py')],
            [sys.executable, str(dist/'crg.pyz'), '--help'],
            [sys.executable, '-I', '-c',
             "import sys; sys.path.insert(0, sys.argv[1]); import crg; from crg.cli import main; assert crg.__file__.startswith(sys.argv[1]); main(['--help'])", str(root/'wheel')],
        ]
        for command in commands:
            subprocess.run(command, cwd=root, env=env, check=True, capture_output=True, text=True, timeout=60)
    return {'result':'PASS', 'checks':len(commands), 'scope':'out-of-tree skill ZIP self-test, PYZ CLI, extracted wheel CLI; no live runtime'}

if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'dist')))
