"""Private immutable artifact primitives; no user-file overwrite."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import os
import stat
import tempfile
import time


def private_directory(path: Path):
    path=path.absolute()
    if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('Symlink storage directory refused')
    missing=[];cursor=path
    while not cursor.exists():missing.append(cursor);cursor=cursor.parent
    for directory in reversed(missing):
        try:directory.mkdir(mode=0o700)
        except FileExistsError:pass
        sync_directory(directory.parent)
    info=path.stat()
    if info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('Storage directory must be private (0700)')
    return path


def read_private(path: Path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        info=os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
            raise ValueError('Unsafe artifact file')
        return f.read()


def sync_directory(path: Path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def immutable_write(path: Path, data: bytes):
    """Atomically install a complete file; retries must match exactly."""
    fd,temp=tempfile.mkstemp(prefix='.crg-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        try:os.link(temp,path)  # exclusive atomic install, never replace existing data
        except FileExistsError:
            if read_private(path)!=data:raise ValueError('Conflicting immutable archive artifact')
        sync_directory(path.parent)
    finally:
        if os.path.exists(temp):os.unlink(temp)


@contextmanager
def exclusive_lock(directory: Path,timeout=10):
    fd=os.open(directory/'.crg.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    deadline=time.monotonic()+timeout
    try:
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise TimeoutError('Archive lock timeout')
                time.sleep(.01)
        yield
    finally:os.close(fd)
