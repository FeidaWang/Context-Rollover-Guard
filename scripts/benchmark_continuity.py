"""Bounded offline protocol benchmark; publishes all successes and failures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from crg.continuity import decide
from crg.appserver import ExecutionSettings
from crg.recovery import reconcile_forward
from tests.unit.test_coordinator import CoordinatorTests,FakeClient,Crash


def scenario(path):
    if path in {'native','observe'}:
        with tempfile.TemporaryDirectory() as tmp:
            client=FakeClient(Path(tmp).resolve());settings=ExecutionSettings.from_start(client.response)
            prompt='synthetic benchmark request'
            if path=='observe':
                assert decide(native_healthy=True,high_pressure=True).value=='OBSERVE'
            client.request('turn/start',settings.turn_params('old',prompt,'benchmark'))
            preserved=client.messages[0]['content'][0]['text']==prompt
            return {'protocol_correct':preserved,'exact_prompt_preserved':preserved,
                    'duplicate_mutations':len(client.messages)-1,'source_retained':True,'recovery_success':None}
    fixture=CoordinatorTests()
    try:
        fixture.setUp()
        # An unobservable real quiet point must retain the source.
        fixture.client.read_activity=lambda thread:{'thread_id':thread,'complete':False}
        if path=='recovery':
            fixture.c.fault=lambda point:(_ for _ in ()).throw(Crash()) if point=='forward:accepted' else None
            try:fixture.c.run(fixture.rid)
            except Crash:pass
            fixture.c.fault=lambda _:None
            blocked=fixture.c.run(fixture.rid)
            assert blocked['state']=='RECOVERY_REQUIRED'
            reconcile_forward(fixture.c,fixture.rid)
        elif path!='handoff':raise ValueError('Unknown benchmark scenario')
        result=fixture.c.run(fixture.rid)
        preserved=fixture.client.messages[0]['content'][0]['text']==fixture.prompt
        duplicates=len(fixture.client.messages)-1
        return {'protocol_correct':result['state']=='NORMAL' and preserved and duplicates==0,
                'exact_prompt_preserved':preserved,'duplicate_mutations':duplicates,
                'source_retained':not result['old_thread_archived'],
                'recovery_success':result['state']=='NORMAL' if path=='recovery' else None}
    finally:fixture.doCleanups()


def run():
    definition=(ROOT/'tests/fixtures/continuity-benchmark.json').read_bytes()
    cases=json.loads(definition)['cases'];rows=[]
    for case in cases:
        start=time.monotonic()
        try:
            metrics=scenario(case['path'])
            row=dict(case,status='PASS' if metrics['protocol_correct'] else 'FAIL',**metrics)
        except Exception as exc:
            row=dict(case,status='FAIL',error_type=type(exc).__name__)
        row.update(elapsed_ms=round((time.monotonic()-start)*1000,3),model_usage=None,
                   final_task_correctness=None,context_compactions=None)
        rows.append(row)
    return {'schema_version':1,'evidence':'OFFLINE_TEST','fixture_sha256':hashlib.sha256(definition).hexdigest(),
            'benchmark_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_commit':subprocess.check_output(['git','rev-parse','--verify','HEAD'],cwd=ROOT,text=True).strip(),
            'source_files':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'crg').rglob('*.py'))},
            'scope':'synthetic protocol comparison; no live task correctness, model usage, or compaction measurements',
            'cases':rows,'all_passed':all(row['status']=='PASS' for row in rows)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'all_passed':report['all_passed'],'case_count':len(report['cases'])}))
    return 0 if report['all_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
