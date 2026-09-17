"""Explicit local identity mapping. Keys and raw identifiers never enter exports."""
import hashlib
import hmac
import os
from pathlib import Path
from .durable import private_directory, read_private


def local_identity(value, key_path):
    path = Path(key_path).absolute(); private_directory(path.parent)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(os.urandom(32)); stream.flush(); os.fsync(stream.fileno())
    key = read_private(path, max_bytes=32)
    if len(key) != 32 or not isinstance(value, str):
        raise ValueError('Invalid identity key or identifier')
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
