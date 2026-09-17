"""Offline sparse-history read cost; includes separate fresh-process startup."""
import json
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crg.ledger import CanonicalLedger
from crg.native_reader import BoundReader


def run():
    startup=[]
    for _ in range(5):
        start=time.perf_counter_ns()
        subprocess.run([sys.executable,'-c','import crg.native_reader'],check=True,stdout=subprocess.DEVNULL)
        startup.append((time.perf_counter_ns()-start)/1e6)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp).resolve();path=root/'history.jsonl'
        with path.open('wb') as out:out.seek(100*1024*1024-1);out.write(b'\n')
        db=CanonicalLedger(root/'private/db')
        try:
            reader=BoundReader(db,path,authorized_root=root,session_id='synthetic',runtime_version='synthetic-v1')
            start=time.perf_counter_ns();cold=reader.read(bootstrap_at_end=True);cold_ms=(time.perf_counter_ns()-start)/1e6
            hot=[];sizes=[]
            for _ in range(100):
                start=time.perf_counter_ns();result=reader.read();hot.append((time.perf_counter_ns()-start)/1e6);sizes.append(result['bytes_read'])
            return {'evidence':'synthetic_local','python':platform.python_version(),'os':platform.system(),'architecture':platform.machine(),
                    'cpu_count':os.cpu_count(),'reader_sha256':hashlib.sha256(Path(__file__).resolve().parents[1].joinpath('crg/native_reader.py').read_bytes()).hexdigest(),'history_bytes':path.stat().st_size,'storage':'local temporary sparse file',
                    'process_startup_ms':startup,'cold_ms':cold_ms,'cold_bytes':cold['bytes_read'],
                    'hot_samples':len(hot),'hot_p95_ms':sorted(hot)[94],'hot_max_bytes':max(sizes),
                    'limitations':'Warm cache, sparse history, no native runtime; not an end-to-end latency guarantee.'}
        finally:db.close()

if __name__=='__main__':print(json.dumps(run(),indent=2))
