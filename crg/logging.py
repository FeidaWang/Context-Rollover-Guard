"""Private diagnostic JSONL; state.json, not this best-effort log, is authoritative."""
from pathlib import Path
import fcntl
import json
import os
from .domain import now


def append_event(path: Path, event: str, *, workspace_id: str, thread_id: str,
                 turn_id: str | None, data: dict, rollover_id: str | None = None):
    # Callers supply only projected counters/decisions; never pass raw protocol events.
    record={"ts":now(),"event":event,"workspace_id":workspace_id,"thread_id":thread_id,
            "turn_id":turn_id,"rollover_id":rollover_id,"data":data}
    encoded=(json.dumps(record,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_APPEND|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        size=os.lseek(fd,0,os.SEEK_END)
        if size and os.pread(fd,1,size-1)!=b'\n':
            os.write(fd,b'\n')  # preserve damaged tail; next complete record stays readable
        offset=0
        while offset<len(encoded):offset+=os.write(fd,encoded[offset:])
        os.fsync(fd)
    finally:os.close(fd)


def read_events(path: Path):
    """Malformed/truncated diagnostic records are ignored; never used for recovery."""
    with path.open('rb') as f:
        for line in f:
            try:
                record=json.loads(line)
                if isinstance(record,dict) and 'event' in record:yield record
            except (ValueError,UnicodeError):continue
