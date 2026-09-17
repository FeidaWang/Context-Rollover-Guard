"""Explicitly bound, bounded JSONL reader; no directory discovery or polling.

A caller supplies a verified adapter. The default consumes normalized v1 records,
not undocumented native transcript fields. Unsupported native schemas stay disabled.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
from .events import project
from .durable import regular_file
from .ledger import identity


class BoundReader:
    def __init__(self, ledger, path, *, authorized_root, session_id, runtime_version,
                 adapter=project, max_bytes=65536, max_line=16384, max_records=128):
        if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW'):
            raise ValueError('UNSUPPORTED_PLATFORM')
        self.ledger, self.path = ledger, Path(path).absolute()
        root = Path(authorized_root).absolute()
        if not self.path.is_relative_to(root) or self.path == root:
            raise ValueError('Unbound input path')
        for value in (session_id, runtime_version):
            if not isinstance(value, str) or not value:
                raise ValueError('Current session and runtime binding required')
        for value in (max_bytes, max_line, max_records):
            if type(value) is not int or value <= 0:
                raise ValueError('Positive read bounds required')
        if max_line > max_bytes or max_records > 1000:
            raise ValueError('Invalid reader limits')
        # Check every parent, including the authorization boundary, before open.
        for parent in [self.path.parent, *self.path.parents]:
            if parent.is_symlink():
                raise ValueError('Symlink parent refused')
        self.source = identity([str(self.path), session_id, runtime_version])
        self.session_id, self.runtime_version = session_id, runtime_version
        self.adapter = adapter
        self.max_bytes, self.max_line, self.max_records = max_bytes, max_line, max_records

    def read(self, *, bootstrap_at_end=False):
        old = self.ledger.cursor(self.source)
        with regular_file(self.path, private=False, max_bytes=2**63-1) as stream:
            fd=stream.fileno()
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise ValueError('Only owned regular files are accepted')
            n = old['prefix_size'] if old else min(256, info.st_size)
            prefix = os.read(fd, n)
            stamp = {'device': info.st_dev, 'inode': info.st_ino,
                     'prefix_size': n, 'prefix_hash': hashlib.sha256(prefix).hexdigest(),
                     'session_id': self.session_id, 'runtime_version': self.runtime_version}
            if old and (any(old[k] != value for k, value in stamp.items()) or info.st_size < old['offset']):
                raise ValueError('SOURCE_CHANGED_REVALIDATION_REQUIRED')
            offset = old['offset'] if old else 0
            if bootstrap_at_end:
                if old:
                    raise ValueError('Bootstrap cannot skip an existing cursor')
                # Never start inside a record: an incomplete tail requires explicit backfill.
                if info.st_size:
                    os.lseek(fd, info.st_size - 1, os.SEEK_SET)
                    if os.read(fd, 1) != b'\n':
                        raise ValueError('Bootstrap requires a complete record boundary')
                offset = info.st_size
            os.lseek(fd, offset, os.SEEK_SET)
            chunk = os.read(fd, self.max_bytes)
            records, consumed = [], 0
            for line in chunk.splitlines(keepends=True):
                if not line.endswith(b'\n'):
                    if len(line) > self.max_line:
                        raise ValueError('Record exceeds line limit')
                    break
                if len(line) > self.max_line:
                    raise ValueError('Record exceeds line limit')
                raw = json.loads(line)
                observation = self.adapter(raw)
                if observation is not None:
                    records.append(observation)
                consumed += len(line)
                if len(records) >= self.max_records:
                    break
            current = os.fstat(fd)
            if current.st_size < offset + consumed:
                raise ValueError('Source truncated during read')
            stamp.update(offset=offset + consumed,
                         coverage_start=old['coverage_start'] if old else offset,
                         partial_tail=consumed < len(chunk),
                         lag_bytes=max(0, current.st_size - offset - consumed))
            self.ledger.ingest(records, source=self.source, expected_cursor=old, cursor=stamp)
            return {'records': len(records), 'bytes_read': len(prefix) + len(chunk),
                    'lag_bytes': stamp['lag_bytes'], 'offset': stamp['offset'],
                    'coverage_start': stamp['coverage_start'], 'model_calls': 0}
