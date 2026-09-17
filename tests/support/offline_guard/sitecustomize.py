"""Inherited offline-test guard; never imported by the production package."""
import os
from pathlib import Path
import sys


def guard(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.bind'}:
        raise RuntimeError('Offline verification forbids network access')
    if event in {'os.system', 'os.exec', 'os.posix_spawn'}:
        raise RuntimeError('Offline verification forbids unguarded process launch')
    if event == 'subprocess.Popen':
        executable = Path(os.fsdecode(args[0]))
        argv = list(args[1])
        git_args = argv[3:] if len(argv) > 2 and argv[1] == '-C' else argv[1:]
        if executable.name == 'git' and git_args in [
            ['rev-parse', '--show-toplevel'], ['rev-parse', '--verify', 'HEAD'],
            ['symbolic-ref', '--short', 'HEAD'],
            ['status', '--porcelain=v1', '-z', '--untracked-files=all']
        ]:
            return
        if executable.resolve() != Path(sys.executable).resolve():
            # The wire tests create this exact synthetic, stdio-only server.
            if executable.name != 'fake-codex' or not executable.is_file() or "print('codex-cli test')" not in executable.read_text():
                raise RuntimeError('Offline verification forbids live runtime launch')


sys.addaudithook(guard)
