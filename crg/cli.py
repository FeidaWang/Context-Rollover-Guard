"""Explicit CLI commands only. No background registration or automatic actions."""
import argparse
from dataclasses import asdict
import json
import sys
import hashlib
from pathlib import Path
from .config import load_config
from .capability_probe import probe


def main(argv=None):
    parser = argparse.ArgumentParser(prog="crg")
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="Own a JSONL chat and automatically route guarded rollovers")
    chat.add_argument("--workspace", type=Path, default=Path.cwd())
    chat.add_argument("--schema", type=Path, default=Path("docs/context-rollover/evidence/schema"))
    chat.add_argument("--model")
    chat.add_argument("--reconcile-run", type=Path, help="Read-only native completion reconciliation; never resend")
    chat.add_argument("--resume-run", type=Path, help="Resume a completed owned-run journal; never replay pending input")
    chat.add_argument("--permissions", help="Named runtime permission profile; default read-only")
    chat.add_argument("--timeout", type=float, default=300)
    doctor = sub.add_parser("doctor", help="Inspect cached capabilities; use --probe for isolated RPC")
    doctor.add_argument("--probe", action="store_true")
    doctor.add_argument("--workspace", type=Path, default=Path.cwd())
    doctor.add_argument("--evidence", type=Path, default=Path("docs/context-rollover/evidence"))
    doctor.add_argument("--surface", default="unknown")
    doctor.add_argument("--codex", help="Override the CRG-configured installed runtime")
    config = sub.add_parser("config", help="Show effective CRG config (never Codex secrets)")
    config.add_argument("--workspace", type=Path, default=Path.cwd())
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
    recovery.add_argument("--schema",type=Path,default=Path("docs/context-rollover/evidence/schema"))
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
    installer.add_argument("--apply",action="store_true")
    uninstaller=sub.add_parser("uninstall-hooks",help="Remove only receipt-owned Hook entries")
    uninstaller.add_argument("--receipt",type=Path,required=True)
    args = parser.parse_args(argv)
    try:
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
                schema=ProtocolSchema(args.schema)
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
                if args.receipt_root is None:raise ValueError("Explicit private receipt root required")
                result=install_hooks(plan,args.receipt_root)
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
            result = asdict(load_config(args.workspace))
        elif args.probe:
            result = probe(args.workspace, args.evidence.resolve(), args.codex or load_config(args.workspace).context_rollover.codex_binary or "codex", args.surface)
            result = {k: v for k, v in result.items() if k != "schema_sha256"}
        else:
            saved = args.evidence / "capabilities.json"
            data = json.loads(saved.read_text()) if saved.exists() else {}
            effective=load_config(args.workspace)
            deployment=args.workspace/"docs/context-rollover/evidence/mode-b-install.json"
            installed=json.loads(deployment.read_text()) if deployment.exists() else {}
            verification_path=args.workspace/"docs/context-rollover/evidence/mode-b-desktop-stop-validation.json"
            verified=json.loads(verification_path.read_text()) if verification_path.exists() else {}
            cached_pass=verified.get("result")=="PASS"
            result = {"configured_mode":effective.context_rollover.mode,
                      "configured_enabled":effective.context_rollover.enabled,
                      "hook_activation":"VERIFIED_AT_LAST_CHECK" if cached_pass else installed.get("hook_trust","NOT_INSTALLED_OR_UNVERIFIED"),
                      "deployment_verified_at":verified.get("checked_at"),
                      "live_activation_verified":False,
                      "evidence_kind": "cached; rerun --probe after upgrade",
                      "codex_version": data.get("codex_version"), "surface": data.get("surface", "unknown"),
                      "selected_mode": effective.context_rollover.mode, "production_enabled": None,
                      "hooks": data.get("schema", {}).get("hooks_supported", {}),
                      "app_server_available": data.get("runtime", {}).get("initialize_ok", False),
                      "context_telemetry": "native Hook record verified at last check" if cached_pass else "not verified",
                      "current_context_window": None, "effective_compact_limit": None,
                      "archive_root": str(load_config(args.workspace).paths(args.workspace)[0]),
                      "state_dir": str(load_config(args.workspace).paths(args.workspace)[1])}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc), "production_enabled": False}))
        return 1
