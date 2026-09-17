#!/usr/bin/env python3
"""Installed entrypoint; stdout contains one Hook protocol object only."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crg.repo_hook import dispatch_repo
from crg.hook_failure import failure_output


def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    event=None
    try:
        raw=sys.stdin.buffer.read(16*1024*1024+1)
        if len(raw)>16*1024*1024:raise ValueError('Hook input exceeds limit')
        event=json.loads(raw)
        result=dispatch_repo(event,a.workspace)
        code=0
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        # No public current-session blocking contract; never pretend exit 1 blocks.
        result,code=failure_output(event,exc)
    print(json.dumps(result,ensure_ascii=False))
    return code


if __name__=='__main__':raise SystemExit(main())
