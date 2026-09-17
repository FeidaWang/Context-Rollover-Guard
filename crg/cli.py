"""Explicit CLI commands only. No background registration or automatic actions."""
import argparse
from dataclasses import asdict
import json
import sys
import hashlib
import sqlite3
from pathlib import Path
from .config import load_config, resolve_config
from .capability_probe import probe


def main(argv=None):
    parser = argparse.ArgumentParser(prog="crg")
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="Own a JSONL chat and automatically route guarded rollovers")
    chat.add_argument("--workspace", type=Path, default=Path.cwd())
    chat.add_argument("--schema", type=Path, default=None)
    chat.add_argument("--model")
    chat.add_argument("--advice-file",type=Path,help="Optional precomputed advice/estimate JSON, displayed separately")
    chat.add_argument("--reconcile-run", type=Path, help="Read-only native completion reconciliation; never resend")
    chat.add_argument("--resume-run", type=Path, help="Resume a completed owned-run journal; never replay pending input")
    chat.add_argument("--permissions", help="Named runtime permission profile; default read-only")
    chat.add_argument("--timeout", type=float, default=300)
    doctor = sub.add_parser("doctor", help="Inspect cached capabilities; use --probe for isolated RPC")
    doctor.add_argument("--probe", action="store_true")
    doctor.add_argument("--workspace", type=Path, default=Path.cwd())
    doctor.add_argument("--evidence", type=Path, default=None)
    doctor.add_argument("--surface", default="unknown")
    doctor.add_argument("--codex", help="Override the CRG-configured installed runtime")
    doctor.add_argument('--format', choices=['json', 'human'], default='json')
    init = sub.add_parser('init', help='Create disabled workspace configuration; never install hooks')
    init.add_argument('--workspace', type=Path, default=Path.cwd())
    config = sub.add_parser("config", help="Show effective CRG config (never Codex secrets)")
    config.add_argument("--workspace", type=Path, default=Path.cwd())
    config.add_argument("--codex", help="User-local runtime override for this inspection")
    for name in ("observe", "status"):
        command=sub.add_parser(name, help="Explicit offline event ingestion" if name=="observe" else "Read session state")
        command.add_argument("--workspace",type=Path,default=Path.cwd())
        command.add_argument("--session",required=True)
        command.add_argument("--state-root",type=Path,required=True)
        if name=="observe":
            command.add_argument("--thread",required=True)
            command.add_argument("--input",type=Path,help="Ordered JSONL App Server notifications; default stdin")
            command.add_argument("--scope",choices=["total","body_after_prefix","unknown"],default="unknown")
            command.add_argument("--compact-limit",type=int)
    hook=sub.add_parser("hook",help="Single dispatcher for an explicitly configured integration")
    hook.add_argument("--workspace",type=Path,required=True)
    hook.add_argument("--session",required=True)
    hook.add_argument("--thread",required=True)
    hook.add_argument("--state-root",type=Path,required=True)
    hook.add_argument("--archive-root",type=Path)
    hook.add_argument("--allow-warning",action="store_true")
    hook.add_argument("--allow-prompt-block",action="store_true")
    hook.add_argument("--allow-precompact-block",action="store_true")
    recovery=sub.add_parser("recover",help="Inspect or positively reconcile an existing transaction; never replay")
    recovery.add_argument("--workspace",type=Path,required=True)
    recovery.add_argument("--transaction-root",type=Path,required=True)
    recovery.add_argument("--archive-root",type=Path,required=True)
    recovery.add_argument("--rollover-id",required=True)
    recovery.add_argument("--reconcile",choices=["forward","archive"])
    recovery.add_argument("--schema",type=Path,default=None)
    listing=sub.add_parser("archive-list",help="Verify archive indexes without displaying prompts/answers")
    listing.add_argument("--archive-root",type=Path,required=True)
    calibration=sub.add_parser("calibrate",help="Summarize verified real boundaries; suggestions only")
    calibration.add_argument("--input",type=Path,required=True)
    boundaries=sub.add_parser("boundary-inventory",help="Read explicit native transcripts; no inferred calibration thresholds")
    boundaries.add_argument("--workspace",type=Path,default=Path.cwd())
    boundaries.add_argument("--input",type=Path,nargs='+',required=True)
    native=sub.add_parser("calibration-evidence",help="Join native exact threshold logs to real completed automatic compactions")
    native.add_argument("--database",type=Path,required=True)
    native.add_argument("--sessions-root",type=Path,nargs='+',required=True)
    installer=sub.add_parser("install-hooks",help="Preview a preserving merge; --apply explicitly writes it")
    installer.add_argument("--hooks-file",type=Path,required=True)
    installer.add_argument("--dispatcher-argv",type=json.loads,required=True,help="JSON array of dispatcher executable and arguments")
    installer.add_argument("--receipt-root",type=Path)
    installer.add_argument("--workspace",type=Path,default=Path.cwd())
    installer.add_argument("--apply",action="store_true")
    uninstaller=sub.add_parser("uninstall-hooks",help="Remove only receipt-owned Hook entries")
    uninstaller.add_argument("--receipt",type=Path,required=True)
    ledger = sub.add_parser('ledger-import', help='Import projected JSONL counters into a private local ledger')
    ledger.add_argument('--database',type=Path,required=True)
    ledger.add_argument('--input',type=Path,required=True)
    usage = sub.add_parser('usage', help='Summarize explicitly recorded local scope; missing usage remains unknown')
    usage.add_argument('--database',type=Path,required=True)
    usage.add_argument('--scope',required=True)
    usage.add_argument('--start',required=True)
    usage.add_argument('--end',required=True)
    qi=sub.add_parser('quota-import',help='Import explicitly supplied projected account snapshots; never redeem quota')
    qi.add_argument('--database',type=Path,required=True);qi.add_argument('--input',type=Path,required=True)
    qs=sub.add_parser('quota-status',help='Read the last account/bucket snapshot with freshness')
    qs.add_argument('--database',type=Path,required=True);qs.add_argument('--account-fingerprint',required=True)
    qs.add_argument('--bucket',required=True);qs.add_argument('--at',required=True)
    advice=sub.add_parser('advise',help='Compute local next-task advice without selecting a model')
    advice.add_argument('--catalog',type=Path,required=True);advice.add_argument('--features',type=Path,required=True)
    advice.add_argument('--policy',type=Path,required=True);advice.add_argument('--history',type=Path)
    advice.add_argument('--database',type=Path);advice.add_argument('--runtime-version')
    advice.add_argument('--format',choices=['json','status'],default='json');advice.add_argument('--estimate',type=Path)
    prediction=sub.add_parser('predict',help='Record a local estimate before starting work')
    prediction.add_argument('--database',type=Path,required=True)
    for field in ('task-class','model','effort','runtime-version'):prediction.add_argument('--'+field,required=True)
    prediction.add_argument('--prediction-id')
    completion=sub.add_parser('complete-observation',help='Join an explicit outcome to a saved pre-task estimate')
    completion.add_argument('--database',type=Path,required=True);completion.add_argument('--input',type=Path,required=True)
    audit = sub.add_parser('statistical-audit', help='Offline time-split quality/cost and interval audit; never activate a policy')
    audit.add_argument('--input', type=Path, required=True, help='Projected observation JSONL')
    audit.add_argument('--split-at', required=True)
    audit.add_argument('--quality-floor', type=float, default=.9)
    audit.add_argument('--minimum-samples', type=int, default=30)
    audit.add_argument('--latency-budget-ms', type=float)
    resolve = sub.add_parser('resolve-model', help='Resolve an explicit model/effort against a supplied runtime catalog')
    resolve.add_argument('--catalog', type=Path, required=True)
    resolve.add_argument('--model', required=True)
    resolve.add_argument('--effort', required=True)
    resolve.add_argument('--at', required=True)
    resolve.add_argument('--expected-revision')
    args = parser.parse_args(argv)
    try:
        if args.command == 'statistical-audit':
            from .statistical_audit import audit
            with args.input.open() as stream:
                rows = [json.loads(line) for line in stream if line.strip()]
            result = audit(rows, split_at=args.split_at, quality_floor=args.quality_floor,
                           minimum_samples=args.minimum_samples, latency_budget_ms=args.latency_budget_ms)
            print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
        if args.command == 'resolve-model':
            from .models import resolve_action
            catalog = json.loads(args.catalog.read_text())
            catalog = catalog.get('runtime', {}).get('model_catalog', catalog)
            result = resolve_action(catalog, model_id=args.model, effort=args.effort,
                                    at=args.at, expected_revision=args.expected_revision)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result['status'] == 'RESOLVED' else 2
        if args.command in {'predict','complete-observation'}:
            from .estimates import Estimates
            if args.command=='complete-observation' and not args.database.is_file():raise ValueError('Existing predictions required')
            estimates=Estimates(args.database)
            try:
                if args.command=='predict':result=estimates.begin(args.task_class,args.model,args.effort,args.runtime_version,prediction_id=args.prediction_id)
                else:
                    estimates.complete(**json.loads(args.input.read_text()));result={'recorded':True,'model_calls':0}
            finally:estimates.close()
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command=='advise':
            from .advisor import recommend
            catalog=json.loads(args.catalog.read_text())
            catalog=catalog.get('runtime',{}).get('model_catalog',catalog)
            history=json.loads(args.history.read_text()) if args.history else None
            if args.database:
                if not args.database.is_file() or not args.runtime_version:raise ValueError('Existing estimate database and runtime version required')
                from .estimates import Estimates
                from .domain import now
                estimates=Estimates(args.database)
                try:history=estimates.quality_history(at=now(),runtime_version=args.runtime_version)
                finally:estimates.close()
            result=recommend(catalog,json.loads(args.features.read_text()),json.loads(args.policy.read_text()),history)
            if args.format=='status':
                from .advice_render import render_status
                print(render_status(result,json.loads(args.estimate.read_text()) if args.estimate else None));return 0
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command in {'quota-import','quota-status'}:
            from .quota import Quotas
            if args.command=='quota-status' and not args.database.is_file():raise ValueError('Existing ledger required')
            quota=Quotas(args.database)
            try:
                if args.command=='quota-import':
                    count=0
                    with args.input.open() as stream:
                        for line in stream:
                            if line.strip():quota.add(json.loads(line));count+=1
                    result={'processed':count,'redemption_performed':False}
                else:result=quota.latest(args.account_fingerprint,args.bucket,at=args.at)
            finally:quota.close()
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command in {'ledger-import','usage'}:
            from .ledger import Ledger
            if args.command=='usage' and not args.database.is_file():raise ValueError('Existing ledger required')
            ledger=Ledger(args.database)
            try:
                if args.command=='ledger-import':
                    count=0
                    with args.input.open() as stream:
                        for line in stream:
                            if line.strip():ledger.add(json.loads(line));count+=1
                    result={'processed':count,'source':'explicit projected import','model_calls':0}
                else:result=ledger.usage(args.scope,args.start,args.end)
            finally:ledger.close()
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command=="chat":
            from .owned_client import run_chat
            return run_chat(args)
        if args.command=="recover":
            from types import SimpleNamespace
            from .coordinator import Coordinator
            from .recovery import transaction_status,reconcile_forward,reconcile_archive
            if not args.transaction_root.is_dir() or not args.archive_root.is_dir():raise ValueError("Existing transaction/archive roots required")
            if not (args.transaction_root/args.rollover_id).is_dir():raise ValueError("Transaction not found")
            client=SimpleNamespace(workspace=args.workspace.resolve())
            if args.reconcile:
                from .appserver import ProtocolSchema,AppServerClient
                from .runtime_paths import RuntimePaths
                paths = RuntimePaths.resolve(args.workspace, load_config(args.workspace))
                schema=ProtocolSchema(args.schema or paths.schema_cache,
                                      manifest_path=None if args.schema else paths.capability_receipt)
                client=AppServerClient(schema.runtime_binary,schema,args.workspace,expected_version=schema.runtime_version)
                client.start()
            try:
                coordinator=Coordinator(args.transaction_root,args.archive_root,client,owned_surface=True)
                result=(reconcile_forward(coordinator,args.rollover_id) if args.reconcile=="forward" else
                        reconcile_archive(coordinator,args.rollover_id) if args.reconcile=="archive" else
                        transaction_status(coordinator,args.rollover_id))
            finally:
                if args.reconcile:client.close()
        elif args.command=="archive-list":
            from .archive import ArchiveManager
            if not args.archive_root.is_dir():raise ValueError("Existing archive root required")
            manager=ArchiveManager(args.archive_root)
            result=[]
            for directory in sorted(manager.root.glob("crg_*")):
                try:result.append(manager.verify(directory))
                except (OSError,ValueError):result.append({"rollover_id":directory.name,"verified":False})
        elif args.command=="calibration-evidence":
            from .native_calibration import collect
            paths=[path for root in args.sessions_root for path in sorted(root.rglob('*.jsonl'))]
            result=collect(args.database,paths)
        elif args.command=="boundary-inventory":
            from .boundaries import inventory
            result=inventory(args.input,workspace=args.workspace)
        elif args.command=="calibrate":
            from .calibration import summarize
            result=summarize([json.loads(line) for line in args.input.read_text().splitlines() if line.strip()])
        elif args.command=="install-hooks":
            from .installer import plan_hooks,install_hooks
            if not isinstance(args.dispatcher_argv,list):raise ValueError("Dispatcher argv must be an array")
            plan=plan_hooks(args.hooks_file,args.dispatcher_argv)
            if args.apply:
                from .runtime_paths import RuntimePaths
                paths = RuntimePaths.resolve(args.workspace, load_config(args.workspace))
                result=install_hooks(plan,args.receipt_root or paths.hook_receipts)
            else:result={"dry_run":True,"events_added":plan["events_added"],"before_sha256":plan["before_sha256"],"after_sha256":plan["after_sha256"],"production_enabled":False}
        elif args.command=="uninstall-hooks":
            from .installer import uninstall_hooks
            result=uninstall_hooks(args.receipt)
        elif args.command=="hook":
            from .state_store import StateStore
            from .hooks import HookDispatcher
            config=load_config(args.workspace)
            if not config.context_rollover.enabled:
                print("{}");return 0
            store=StateStore(args.state_root,args.workspace,args.session)
            state=store.read()
            if state is None or state.thread_id!=args.thread:raise ValueError("Hook thread binding unavailable")
            dispatcher=HookDispatcher(store,config,allow_warning=args.allow_warning,
                allow_prompt_block=args.allow_prompt_block,allow_precompact_block=args.allow_precompact_block,
                archive_root=args.archive_root or config.paths(args.workspace)[0])
            result=dispatcher.dispatch(json.load(sys.stdin))
        elif args.command in {"observe","status"}:
            from .state_store import StateStore
            from .domain import SessionState,workspace_id
            from .telemetry import Observer
            if args.command=="status":
                directory=args.state_root/"workspaces"/workspace_id(args.workspace)/"sessions"/hashlib.sha256(args.session.encode()).hexdigest()
                if not directory.exists():
                    print(json.dumps({"state":None,"reason":"NOT_INITIALIZED"}));return 0
            store=StateStore(args.state_root,args.workspace,args.session)
            if args.command=="status":
                state=store.read()
                result=state.to_dict() if state else {"state":None}
            else:
                observer=Observer(store,load_config(args.workspace),
                                  initial=SessionState.create(args.workspace,args.session,args.thread),
                                  scope=args.scope,configured_limit=args.compact_limit)
                source=args.input.open() if args.input else sys.stdin
                try:
                    for line in source:
                        if line.strip():print(json.dumps(observer.ingest(json.loads(line)),ensure_ascii=False))
                finally:
                    if args.input:source.close()
                return 0
        elif args.command == "config":
            overrides = {"context_rollover": {"codex_binary": args.codex}} if args.codex is not None else None
            effective, sources = resolve_config(args.workspace, overrides=overrides)
            result = asdict(effective)
            result["sources"] = sources
        elif args.command == 'init':
            from .diagnostics import initialize
            result = initialize(args.workspace)
        else:
            from .runtime_paths import RuntimePaths
            from .diagnostics import diagnose, render_human
            effective, sources = resolve_config(args.workspace)
            paths = RuntimePaths.resolve(args.workspace, effective, evidence=args.evidence)
            if args.probe:
                probe(args.workspace, paths.capability_receipt.parent,
                      args.codex or effective.context_rollover.codex_binary or 'codex', args.surface,
                      paths=paths)
            result = diagnose(args.workspace, effective, sources, evidence=args.evidence, binary=args.codex)
            if args.format == 'human':
                print(render_human(result))
                return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc), "production_enabled": False}))
        return 1
