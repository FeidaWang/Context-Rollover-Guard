"""Verify a clean source snapshot without credentials, private evidence, or network."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def verify(root):
    if (root/'docs/context-rollover/evidence').exists():
        raise RuntimeError('Use --clean to exclude ignored private evidence')
    with tempfile.TemporaryDirectory(prefix='crg-offline-home-') as tmp:
        env = dict(os.environ, HOME=tmp, CODEX_HOME=tmp+'/codex',
                   PYTHONPATH=str(root/'tests/support/offline_guard')+os.pathsep+str(root),
                   PYTHONDONTWRITEBYTECODE='1')
        python = sys.executable
        run([python, '-m', 'unittest', 'discover', '-s', 'tests/unit', '-v'], root, env)
        run([python, '-m', 'unittest', 'discover', '-s', 'tests/integration', '-v'], root, env)
        run([python, 'scripts/build_release.py'], root, env)
        run([python, 'scripts/build_release.py', '--verify'], root, env)
        run([python, 'dist/context-rollover-guard/scripts/self_test.py'], root, env)
        # Also execute the exported ZIP as an independent installation.
        import zipfile
        with zipfile.ZipFile(root/'dist/context-rollover-guard.zip') as bundle:
            bundle.extractall(Path(tmp)/'exported')
        run([python, str(Path(tmp)/'exported/context-rollover-guard/scripts/self_test.py')], root, env)



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true', help='Snapshot non-ignored files into a temporary clean Git checkout')
    args = parser.parse_args()
    if not args.clean:
        verify(ROOT)
        return
    names = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    with tempfile.TemporaryDirectory(prefix='crg-clean-') as tmp:
        root = Path(tmp)/'checkout'
        root.mkdir()
        for name in set(names)-{''}:
            source = ROOT/name
            if source.is_file():
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        run(['git', 'init', '-q'], root)
        run(['git', 'add', '.'], root)
        run(['git', '-c', 'user.name=Offline Test', '-c', 'user.email=offline@example.invalid', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Offline verification snapshot'], root)
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root)
        verify(root)


if __name__ == '__main__':
    main()
