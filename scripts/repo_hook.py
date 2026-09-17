#!/usr/bin/env python3.13
"""Installed absolute-path entrypoint; JSON stdout is exclusively the Hook protocol."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from crg.repo_hook import dispatch_repo
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
try:
    result=dispatch_repo(json.load(sys.stdin),a.workspace)
    print(json.dumps(result,ensure_ascii=False))
except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
    print(json.dumps({'systemMessage':'CRG MODE_B 未完成本次处理：'+type(exc).__name__+'。请检查本地状态；未执行任务切换。'},ensure_ascii=False))
    raise SystemExit(0)
