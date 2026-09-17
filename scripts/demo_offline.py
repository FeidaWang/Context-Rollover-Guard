"""Run the shipped CLI in a disposable workspace without installing any hooks."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    cli = root / 'dist/context-rollover-guard/scripts/crg.pyz'
    with tempfile.TemporaryDirectory(prefix='crg-demo-') as directory:
        base = Path(directory).resolve()
        workspace = base / 'project'
        workspace.mkdir()
        home = base / 'home'
        home.mkdir()
        codex = base / 'codex'
        codex.mkdir()
        env = dict(HOME=str(home), CODEX_HOME=str(codex), PATH='',
                   PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=str(root / 'tests/support/offline_guard'))

        def run(*args):
            result = subprocess.run([sys.executable, str(cli), *map(str, args)],
                                    cwd=workspace, env=env, check=True,
                                    capture_output=True, text=True, timeout=20)
            return json.loads(result.stdout)

        run('init', '--workspace', workspace)
        config = run('config', '--workspace', workspace)
        if config['context_rollover']['enabled'] is not False:
            raise RuntimeError('New workspace unexpectedly enabled CRG')
        diagnosis = run('doctor', '--workspace', workspace)
        hooks = workspace / 'hooks.json'
        preview = run('install-hooks', '--workspace', workspace, '--hooks-file', hooks,
                      '--dispatcher-argv', json.dumps([sys.executable, str(cli), '--help']))
        if not preview.get('dry_run') or hooks.exists():
            raise RuntimeError('Hook preview unexpectedly wrote configuration')
        # The dispatcher above is a preview placeholder, not a live integration.
        print(json.dumps({'result': 'PASS', 'checks': ['init', 'config', 'doctor',
                                                     'hook-preview-no-write'],
                          'scope': 'temporary offline CLI demo; no runtime or hook activation',
                          'config': config, 'diagnosis': diagnosis,
                          'preview': preview}, indent=2))


if __name__ == '__main__':
    main()
