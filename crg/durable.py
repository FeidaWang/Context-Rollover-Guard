"""Private immutable artifact primitives; no user-file overwrite."""
from contextlib import contextmanager
from pathlib import Path
import errno
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


@contextmanager
def regular_file(path: Path, *, private=True, max_bytes=256*1024*1024):
    """Pin every parent with openat; never follow a substituted parent symlink.

    POSIX only. Ancestor renames keep the opened inode pinned. This is not a
    sandbox against an attacker running as the same uid or a hostile filesystem.
    """
    path=Path(path).absolute()
    parent=os.open(path.anchor,os.O_RDONLY|os.O_DIRECTORY)
    fd=None
    try:
        for part in path.parts[1:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            os.close(parent);parent=child
        # Reject devices before open (opening a device can itself have effects).
        before=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
        if stat.S_ISLNK(before.st_mode):raise OSError(errno.ELOOP,'Symlink artifact refused')
        if not stat.S_ISREG(before.st_mode):raise ValueError('Nonregular artifact refused')
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                or private and info.st_mode&0o077
                or (before.st_dev,before.st_ino)!=(info.st_dev,info.st_ino)
                or info.st_size>max_bytes):
            raise ValueError('Unsafe or oversized artifact file')
        with os.fdopen(fd,'rb') as stream:
            fd=None
            yield stream
    finally:
        if fd is not None:os.close(fd)
        os.close(parent)


def read_private(path: Path, *, max_bytes=256*1024*1024):
    with regular_file(path,max_bytes=max_bytes) as stream:
        data=stream.read(max_bytes+1)
        if len(data)>max_bytes:raise ValueError('Artifact grew beyond size limit')
        return data


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


def open_private_lock(path: Path):
    """Open a bounded regular lock inode through pinned, no-follow parents."""
    path=Path(path).absolute()
    parent=os.open(path.anchor,os.O_RDONLY|os.O_DIRECTORY)
    fd=None
    try:
        for part in path.parts[1:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            os.close(parent);parent=child
        for attempt in range(3):
            try:before=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
            except FileNotFoundError:before=None
            if before is not None and not stat.S_ISREG(before.st_mode):
                raise ValueError('Nonregular lock refused')
            flags=os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK
            if before is None:flags|=os.O_CREAT|os.O_EXCL
            try:
                fd=os.open(path.name,flags,0o600,dir_fd=parent)
                break
            except FileExistsError:
                # Local lock creation only, before any business mutation/RPC.
                # Reinspect a concurrent creator rather than trusting its inode.
                continue
        else:raise ValueError('Unstable lock path')
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                or info.st_mode&0o077 or info.st_size>4096
                or before is not None and (before.st_dev,before.st_ino)!=(info.st_dev,info.st_ino)):
            raise ValueError('Unsafe lock file')
        result=fd;fd=None
        return result
    finally:
        if fd is not None:os.close(fd)
        os.close(parent)


@contextmanager
def exclusive_lock(directory: Path,timeout=10):
    fd=open_private_lock(directory/'.crg.lock')
    deadline=time.monotonic()+timeout
    try:
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise TimeoutError('Archive lock timeout')
                time.sleep(.01)
        yield
    finally:os.close(fd)
