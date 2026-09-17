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
    chat = sub.add_parser("chat", help="Own a JSONL chat with explicit fresh-task routing")
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
    doctor.add_argument("--evidence-root", "--evidence", dest="evidence", type=Path, default=None)
    doctor.add_argument("--surface", default="unknown")
    doctor.add_argument("--codex", help="Override the CRG-configured installed runtime")
    doctor.add_argument('--format', choices=['json', 'human'], default='json')
    init = sub.add_parser('init', help='Create disabled workspace configuration; never install hooks')
    init.add_argument('--workspace', type=Path, default=Path.cwd())
    config = sub.add_parser("config", help="Show effective CRG config (never Codex secrets)")
    config.add_argument('action', nargs='?', choices=['show', 'migrate'], default='show')
    config.add_argument("--workspace", type=Path, default=Path.cwd())
    config.add_argument("--codex", help="User-local runtime override for this inspection")
    migration_mode = config.add_mutually_exclusive_group()
    migration_mode.add_argument('--dry-run', action='store_true')
    migration_mode.add_argument('--apply', action='store_true')
    config.add_argument('--output', type=Path)
    config.add_argument('--expected-sha256')
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
    fn=sub.add_parser('forecast-next',help='Persist a confirmed task forecast before execution; no inference')
    fn.add_argument('--database',type=Path,required=True);fn.add_argument('--intent',type=Path,required=True)
    fn.add_argument('--policy',type=Path,required=True);fn.add_argument('--at',required=True)
    fn.add_argument('--target',choices=['wall_ms','active_ms','total_tokens'],default='wall_ms')
    fo=sub.add_parser('forecast-outcome',help='Record an externally observed target or correction')
    fo.add_argument('--database',type=Path,required=True);fo.add_argument('--input',type=Path,required=True)
    qc=sub.add_parser('task-capacity',help='Conditional comparable-task estimate from supplied bucket evidence')
    qc.add_argument('--input',type=Path,required=True)
    ni=sub.add_parser('analytics-import',help='Bounded import of explicitly authorized normalized v1 JSONL')
    ni.add_argument('--database',type=Path,required=True);ni.add_argument('--input',type=Path,required=True)
    ni.add_argument('--authorized-root',type=Path,required=True)
    ni.add_argument('--session',required=True);ni.add_argument('--runtime-version',required=True)
    ni.add_argument('--bootstrap-at-end',action='store_true')
    panel=sub.add_parser('analytics-status',help='Content-free local status; account adapter may be unsupported')
    panel.add_argument('--database',type=Path,required=True);panel.add_argument('--at',required=True)
    panel.add_argument('--scope',choices=['local','account','unknown'],default='local')
    panel.add_argument('--window',choices=['calendar_week','rolling_168h'],default='calendar_week')
    panel.add_argument('--timezone',default='UTC');panel.add_argument('--format',choices=['json','human'],default='json')
    ep=sub.add_parser('export-preview',help='Preview numeric-only analytics; no file write or upload')
    ep.add_argument('--database',type=Path,required=True)
    ew=sub.add_parser('export-write',help='Write the exact previously reviewed export; never upload')
    ew.add_argument('--preview',type=Path,required=True);ew.add_argument('--output',type=Path,required=True)
    ew.add_argument('--approved-sha256',required=True)
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
    resolve.add_argument('--schema', type=Path)
    resolve.add_argument('--manifest', type=Path)
    resolve.add_argument('--binding', type=Path, help='Trusted adapter runtime/account scope projection; no credentials')
    resolve.add_argument('--authorized-params', type=Path, help='Already authorized turn envelope; preparation only')
    resolve.add_argument('--execution-mode', default='single_agent')
    resolve.add_argument('--service-tier')
    resolve.add_argument('--permission-profile')
    args = parser.parse_args(argv)
    try:
        if args.command in {'forecast-next','forecast-outcome'}:
            from .forecast import Forecasts
            from .features import features
            if args.command=='forecast-outcome' and not args.database.is_file():
                raise ValueError('Existing pre-execution forecast required')
            forecasts=Forecasts(args.database)
            try:
                if args.command=='forecast-next':
                    snapshot=features(json.loads(args.intent.read_text()),json.loads(args.policy.read_text()),at=args.at)
                    result=forecasts.predict(snapshot,target=args.target)
                else:
                    forecasts.complete(**json.loads(args.input.read_text()));result={'recorded':True,'model_calls':0}
            finally:forecasts.close()
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command=='task-capacity':
            from .quota_forecast import capacity
            print(json.dumps(capacity(**json.loads(args.input.read_text())),indent=2));return 0
        if args.command in {'analytics-import','analytics-status','export-preview'}:
            from .ledger import CanonicalLedger
            if args.command != 'analytics-import' and not args.database.is_file():
                raise ValueError('Existing analytics database required; unknown is not zero')
            ledger=CanonicalLedger(args.database)
            try:
                if args.command=='analytics-import':
                    from .native_reader import BoundReader
                    result=BoundReader(ledger,args.input,authorized_root=args.authorized_root,
                        session_id=args.session,runtime_version=args.runtime_version).read(bootstrap_at_end=args.bootstrap_at_end)
                elif args.command=='analytics-status':
                    from .account import interval
                    from .presentation import status,human
                    start,end=interval(args.window,at=args.at,timezone_name=args.timezone)
                    result=status(ledger.usage(args.scope,start,end))
                    if args.format=='human':
                        print(human(result));return 0
                else:
                    from .export import preview
                    rows=ledger.db.execute('SELECT payload FROM fact LIMIT 1001').fetchall()
                    if len(rows)>1000:raise ValueError('Export exceeds bounded preview; narrow the dataset first')
                    result=preview([json.loads(row[0]) for row in rows])
            finally:ledger.close()
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if args.command=='export-write':
            from .export import write_approved
            result=write_approved(json.loads(args.preview.read_text()),args.output,approved_sha256=args.approved_sha256)
            print(json.dumps(result));return 0
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
            from .appserver import ProtocolSchema
            schema = ProtocolSchema(args.schema, manifest_path=args.manifest) if args.schema else None
            result = resolve_action(catalog, model_id=args.model, effort=args.effort,
                                    at=args.at, expected_revision=args.expected_revision, schema=schema,
                                    binding=json.loads(args.binding.read_text()) if args.binding else None,
                                    authorized_params=json.loads(args.authorized_params.read_text()) if args.authorized_params else None,
                                    execution_mode=args.execution_mode, service_tier=args.service_tier,
                                    permission_profile=args.permission_profile)
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
            recovery_config=load_config(args.workspace)
            client=SimpleNamespace(workspace=args.workspace.resolve())
            if args.reconcile:
                from .appserver import ProtocolSchema,AppServerClient
                from .runtime_paths import RuntimePaths
                paths = RuntimePaths.resolve(args.workspace, recovery_config)
                schema=ProtocolSchema(args.schema or paths.schema_cache,
                                      manifest_path=None if args.schema else paths.capability_receipt)
                client=AppServerClient(schema.runtime_binary,schema,args.workspace,expected_version=schema.runtime_version)
                client.start()
            try:
                coordinator=Coordinator(args.transaction_root,args.archive_root,client,owned_surface=True,
                                        archive_source=recovery_config.rollover.archive_old_thread)
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
            from .hook_failure import failure_output
            event=None
            config_error=None
            try:config=load_config(args.workspace)
            except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:config_error=exc
            if config_error is None and not config.context_rollover.enabled:
                print("{}");return 0
            try:
                raw=sys.stdin.read(16*1024*1024+1)
                if len(raw)>16*1024*1024:raise ValueError('Hook input exceeds limit')
                event=json.loads(raw)
                if config_error is not None:raise config_error
                store=StateStore(args.state_root,args.workspace,args.session)
                state=store.read()
                if state is None or state.thread_id!=args.thread:raise ValueError("Hook thread binding unavailable")
                # Legacy flags are requests, not verified current-session capability.
                # Keep stdout non-blocking until an adapter provides that contract.
                dispatcher=HookDispatcher(store,config,allow_warning=False,
                    allow_prompt_block=False,allow_precompact_block=False,
                    archive_root=args.archive_root or config.paths(args.workspace)[0])
                result=dispatcher.dispatch(event)
            except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
                result,code=failure_output(event,exc)
                print(json.dumps(result,ensure_ascii=False))
                return code
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
            if args.action == 'migrate':
                from .config_migration import migrate
                if args.codex is not None:
                    raise ValueError('Migration preserves the source runtime setting; --codex is inspection-only')
                result = migrate(args.workspace, apply=args.apply, output=args.output,
                                 expected_sha256=args.expected_sha256)
            else:
                if args.apply or args.dry_run or args.output is not None or args.expected_sha256 is not None:
                    raise ValueError('Migration options require config migrate')
                from .config import migration_diagnostics
                overrides = {"context_rollover": {"codex_binary": args.codex}} if args.codex is not None else None
                effective, sources = resolve_config(args.workspace, overrides=overrides)
                result = asdict(effective)
                result["sources"] = sources
                result['warnings'] = migration_diagnostics(effective, sources)
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
