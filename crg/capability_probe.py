"""Installed-binary schema plus isolated, non-mutating RPC capability probes."""
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import os
import selectors
import shutil
import subprocess
import time
import tomllib
from .domain import now

METHODS = ("thread/start", "turn/start", "thread/archive", "config/read", "hooks/list")
EVENTS = ("stop", "userPromptSubmit", "preCompact", "postCompact", "sessionStart")


def select_mode(evidence: dict) -> str:
    # Missing/unknown/strings are not proof. Presence of an RPC schema is insufficient.
    verified = lambda key: evidence.get(key) is True
    guarded = all(verified(k) for k in ("stop_payload_verified", "prompt_interception_verified",
                                      "hook_execution_trusted", "lossless_answer_verified"))
    controlled = all(verified(k) for k in ("owns_active_transport", "fresh_thread_verified",
        "same_cwd_verified", "exact_once_verified", "archive_order_verified"))
    if guarded and controlled:
        return "MODE_C"
    return "MODE_B" if guarded else "MODE_A"


def inspect_schema(root: Path) -> dict:
    def read(name):
        files = list(root.rglob(name + ".json"))
        return json.loads(files[0].read_text()) if files else {}
    request = read("ClientRequest")
    notification = read("ServerNotification")
    def method_names(doc):
        return {name for variant in doc.get("oneOf", [])
                for name in variant.get("properties", {}).get("method", {}).get("enum", [])}
    methods, notifications = method_names(request), method_names(notification)
    start = read("ThreadStartParams").get("properties", {})
    turn = read("TurnStartParams").get("properties", {})
    hooks = read("HooksListResponse").get("definitions", {}).get("HookEventName", {}).get("enum", [])
    usage = read("ThreadTokenUsageUpdatedNotification").get("definitions", {})
    usage_fields = usage.get("ThreadTokenUsage", {}).get("properties", {})
    breakdown = usage.get("TokenUsageBreakdown", {}).get("properties", {})
    return {
        "methods": {m: m in methods for m in METHODS},
        "token_usage_supported": "thread/tokenUsage/updated" in notifications and
            all(k in usage_fields for k in ("last", "total", "modelContextWindow")) and "totalTokens" in breakdown,
        "compaction_notifications": sorted(n for n in notifications if "/" in n and "compact" in n.lower()),
        "hooks_supported": {e: e in hooks for e in EVENTS},
        "developer_instructions_supported": "developerInstructions" in start,
        "client_user_message_id_supported": "clientUserMessageId" in turn,
        "model_context_window_schema": "modelContextWindow" in usage_fields,
        "thread_start_fields": sorted(start), "turn_start_fields": sorted(turn),
    }


def isolated_rpc(binary: str, workspace: Path) -> dict:
    with TemporaryDirectory(prefix="crg-probe-") as tmp:
        root = Path(tmp).resolve()
        home, project = root / "home", root / "workspace"
        home.mkdir(mode=0o700); project.mkdir(); (project / ".codex").mkdir()
        (home / "config.toml").write_text(f'[projects.{json.dumps(str(project))}]\ntrust_level = "trusted"\n')
        events = ("Stop", "UserPromptSubmit", "PreCompact", "PostCompact", "SessionStart")
        (project / ".codex/hooks.json").write_text(json.dumps({"hooks": {
            e: [{"hooks": [{"type": "command", "command": "/usr/bin/true", "timeout": 10}]}]
            for e in events}}))
        env = os.environ.copy()
        env["CODEX_HOME"] = str(home)
        # No models, real threads, real prompts or hook trust modifications.
        with (root / "stderr.log").open("wb") as err:
            p = subprocess.Popen([binary, "app-server", "--stdio"], cwd=project, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
            selector = selectors.DefaultSelector(); selector.register(p.stdout, selectors.EVENT_READ)
            buffer = b""
            def rpc(i, method, params):
                nonlocal buffer
                p.stdin.write((json.dumps({"id": i, "method": method, "params": params}) + "\n").encode())
                p.stdin.flush()
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        msg = json.loads(line)
                        if msg.get("id") == i:
                            return msg
                    if selector.select(min(1, max(0, deadline - time.monotonic()))):
                        chunk = os.read(p.stdout.fileno(), 65536)
                        if not chunk:
                            raise RuntimeError("App Server EOF")
                        buffer += chunk
                raise TimeoutError(method)
            result = {}
            try:
                init = rpc(1, "initialize", {"clientInfo": {"name": "crg_probe", "version": "0.1.0"},
                                                "capabilities": {"experimentalApi": True}})
                result["initialize_ok"] = "result" in init
                result["user_agent"] = init.get("result", {}).get("userAgent")
                if not result["initialize_ok"]:
                    return result
                p.stdin.write(b'{"method":"initialized"}\n'); p.stdin.flush()
                hooks = rpc(2, "hooks/list", {"cwds": [str(project), str(workspace)]})
                result["hooks_list_ok"] = "result" in hooks
                result["hook_parser"] = [{"event": h["eventName"], "timeout_sec": h["timeoutSec"],
                    "trust": h["trustStatus"], "source": h["source"]}
                    for entry in hooks.get("result", {}).get("data", [])
                    if entry["cwd"] == str(project) for h in entry["hooks"]]
                result["hook_errors"] = sum(len(e.get("errors", []))
                    for e in hooks.get("result", {}).get("data", []))
                cfg = rpc(3, "config/read", {"cwd": str(project), "includeLayers": False})
                result["config_read_ok"] = "result" in cfg
                config = cfg.get("result", {}).get("config", {})
                result["isolated_compact_fields"] = {k: config.get(k) for k in (
                    "model_context_window", "model_auto_compact_token_limit", "model_auto_compact_token_limit_scope")}
                result["invalid_parameter_dispatch"] = {}
                for i, m in enumerate(METHODS[:3], 4):
                    reply = rpc(i, m, {"cwd": 42} if m == "thread/start" else {})
                    result["invalid_parameter_dispatch"][m] = reply.get("error", {})
                return result
            finally:
                p.stdin.close()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.terminate()
                    try:
                        p.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        p.kill(); p.wait()
                p.stdout.close(); selector.close()


def inventory(workspace: Path) -> dict:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    roots = list(reversed(workspace.parents)) + [workspace]
    agent_paths=[p / name for p in roots for name in ("AGENTS.md","AGENTS.override.md")]
    agent_paths += [codex_home / "AGENTS.md",codex_home / "AGENTS.override.md"]
    agents = [{"path":str(p),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
              for p in agent_paths if p.is_file()]
    paths = [p / ".codex" / f for p in roots for f in ("config.toml", "hooks.json")]
    paths += [codex_home / "config.toml", codex_home / "hooks.json"]
    files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    skill_roots = [workspace / ".agents/skills", codex_home / "skills", Path.home() / ".agents/skills"]
    skills = {str(p): sorted(x.name for x in p.iterdir() if x.is_dir()) for p in skill_roots if p.is_dir()}
    config = {}
    p = codex_home / "config.toml"
    if p.exists():
        d = tomllib.loads(p.read_text())
        config = {k: d.get(k) for k in ("model", "model_context_window", "model_auto_compact_token_limit",
                                      "model_auto_compact_token_limit_scope")}
        config["hooks_inline_present"] = "hooks" in d
        config["notify_present"] = "notify" in d
        config["workspace_trust"] = [{"path": k, "trust_level": v.get("trust_level")}
            for k, v in d.get("projects", {}).items() if workspace == Path(k) or Path(k) in workspace.parents]
    git = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=workspace,
                         capture_output=True, text=True)
    return {"workspace": str(workspace), "git_root": git.stdout.strip() if git.returncode == 0 else None,
            "agents_md": agents, "existing_config_sha256": files, "skills": skills,
            "codex_config_allowlist": config}


def probe(workspace: Path, out: Path, binary: str = "codex", surface: str = "unknown") -> dict:
    workspace = workspace.resolve(); out.mkdir(parents=True, exist_ok=True)
    result = {"generated_at": now(), "surface": surface, "selected_mode": "MODE_A", "errors": []}
    try:
        result["inventory"] = inventory(workspace)
    except (OSError, ValueError) as exc:
        result["errors"].append(f"inventory: {type(exc).__name__}")
    executable = shutil.which(binary)
    result["binary"] = executable
    if executable:
        try:
            version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=15)
            result["codex_version"] = version.stdout.strip()
            daemon=subprocess.run([executable,"app-server","daemon","version"],capture_output=True,text=True,timeout=15)
            result["daemon_control_probe"]={"available":daemon.returncode==0,"exit_code":daemon.returncode,
                "reason":"control_socket_missing" if "No such file or directory" in daemon.stderr
                         else "see installed daemon version command"}

            with TemporaryDirectory(prefix="crg-schema-") as tmp:
                schema=Path(tmp)
                generated = subprocess.run([executable, "app-server", "generate-json-schema", "--experimental",
                                            "--out", str(schema)], capture_output=True, text=True, timeout=30)
                result["schema_generation_ok"] = generated.returncode == 0
                if generated.returncode == 0:
                    result["schema"] = inspect_schema(schema)
                    result["schema_sha256"] = {str(p.relative_to(schema)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                for p in sorted(schema.rglob("*.json"))}
                    # Inspect only a fresh generated bundle, never stale files from a prior version.
                    shutil.copytree(schema,out/"schema",dirs_exist_ok=True)
            result["runtime"] = isolated_rpc(executable, workspace)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            result["errors"].append(f"probe: {type(exc).__name__}: {exc}")
    else:
        result["errors"].append("Codex executable unavailable")
    result["selected_mode"] = select_mode(result)
    (out / "capabilities.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (out.parent / "CAPABILITY_REPORT.md").write_text(render_report(result))
    return result


def render_report(d: dict) -> str:
    schema, runtime = d.get("schema", {}), d.get("runtime", {})
    parsed = {h["event"] for h in runtime.get("hook_parser", [])}
    def hook_status(event):
        if event in parsed and schema.get("hooks_supported", {}).get(event) is True:
            return "PARTIAL: event and config parser verified; process payload/effects unverified"
        return "UNVERIFIED: no complete installed parser evidence"
    rows = {
        "codex_version": d.get("codex_version", "unavailable"),
        "surface": d.get("surface", "unknown") + " (caller-declared; detached CLI probed)",
        "hooks_supported": schema.get("hooks_supported", {}),
        "stop_schema_ok": hook_status("stop"),
        "user_prompt_submit_schema_ok": hook_status("userPromptSubmit"),
        "precompact_schema_ok": hook_status("preCompact"),
        "session_start_schema_ok": hook_status("sessionStart"),
        "app_server_available": runtime.get("initialize_ok", False),
        "thread_start_supported": schema.get("methods", {}).get("thread/start", False),
        "turn_start_supported": schema.get("methods", {}).get("turn/start", False),
        "thread_archive_supported": schema.get("methods", {}).get("thread/archive", False),
        "token_usage_supported": schema.get("token_usage_supported", False),
        "developer_instructions_supported": schema.get("developer_instructions_supported", False),
        "model_context_window_observable": "active Desktop stream not connected; see schema support below",
        "auto_compact_limit_observable": runtime.get("isolated_compact_fields", "unverified"),
        "repo_local_hooks_trusted": runtime.get("hook_parser", []),
        "selected_mode": d.get("selected_mode", "MODE_A"),
        "errors": d.get("errors", []),
        "daemon_control_probe": d.get("daemon_control_probe", "not probed"),
    }
    table = '\n'.join(f'| {k} | {json.dumps(v, ensure_ascii=False) if not isinstance(v,str) else v} |'
                      for k,v in rows.items())
    inventory_json = json.dumps(d.get("inventory", {}), ensure_ascii=False, indent=2)
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
    return f'''# CRG Capability Report

Generated: {d.get("generated_at")}

## Runtime evidence

| Capability | Result |
|---|---|
{table}

Evidence: [capabilities.json](evidence/capabilities.json),
[installed protocol schema](evidence/schema/ClientRequest.json),
[token notification](evidence/schema/v2/ThreadTokenUsageUpdatedNotification.json),
[Hook metadata](evidence/schema/v2/HooksListResponse.json).
The JSON evidence includes SHA-256 for every current generated schema file and existing user configurations.
No raw environment, auth, MCP configuration, transcript, prompt or answer is copied.

Probe commands: `codex --version`; `codex app-server generate-json-schema --experimental --out <evidence/schema>`;
isolated `codex app-server --stdio`, `initialize`, `initialized`, `hooks/list`, `config/read`.
Invalid-parameter requests check dispatch for `thread/start`, `turn/start`, `thread/archive` without
creating threads, submitting prompts, running hooks or archiving anything. Inspect response codes
in evidence: schema/dispatch presence is not an end-to-end guarantee. Probe home and synthetic hook
configuration are isolated temporary files. No individual hook is trusted or executed by the probe.

## Repository and configuration inspection

```json
{inventory_json}
```

A null git_root means no repository was detected. Existing config files are read and hashed only.
The supplied initial workspace was empty; a standalone package was created at
`outputs/context-rollover-guard/`, without git init/commit/push. See INITIAL_ENVIRONMENT.md for
that dated implementation-specific inspection, including existing skills and runtime limits.

## Installed schema extraction

```json
{schema_json}
```

## Capability differences and compatibility policy

- Compare current `hooks_supported` and `hook_parser` above: protocol enums use lower camel case;
  the probe submits PascalCase config events. Parser metadata exposes `timeoutSec` for config
  `timeout`. Only events actually returned by the installed parser count as parser-verified.
- Project trust and per-hook hash trust are separate. App Server Hook metadata schemas do not
  constitute full process stdin/stdout schemas. Never infer blocking or lossless answer capture
  from event existence. The installed metadata lacks the PreCompact trigger; the observer records
  `unknown`, not a fabricated `auto` trigger.
- Check the current ThreadStartParams and TurnStartParams schemas. In the initially verified
  0.139.0 bundle, thread permissions/sandbox and turn permissions/sandboxPolicy are exclusive;
  reasoning effort is a turn `effort` field. `turn/start` requires typed `input` and `threadId`.
  These statements are version-scoped; generated schemas control future adapters.
- `clientUserMessageId` field presence does not prove server-side retry deduplication. Ambiguous
  acceptance must require reconciliation rather than a blind resend.
- Where verified, active context is `tokenUsage.last.totalTokens`; cumulative session usage is
  `tokenUsage.total.totalTokens`. Never substitute the latter for unavailable active data.
  Window and compact overrides can be null. No model-name context constants are used.
- Derived compact thresholds are estimates. Unknown scope uses a configurable conservative line;
  body-after-prefix thresholds cannot be called precise without prefix visibility.
- CRG does not own the active Desktop transport. Detached availability is not UI switching
  authority. No fresh thread/fork/UI mutation occurs during probing.
- Safe defaults intentionally differ from the roadmap example: disabled, MODE_A, blocking off.

## Mode decision and limitations

MODE_A is the fail-safe selection until stronger evidence exists. MODE_B requires verified lossless
Stop payload, trusted hook execution and prompt interception. MODE_C additionally requires active
transport ownership, fresh same-cwd behavior and verified acceptance/deduplication/archive ordering.
No hook execution, live multi-turn telemetry, actual compact boundary or UI attachment is proven by
this probe. Unknown values remain unknown. Re-probe after upgrading Codex; the SHA manifest identifies
the active bundle even if older generated files remain on disk.

## Supplemental documentation (not runtime authority)

[Official Hooks documentation](https://learn.chatgpt.com/docs/hooks) describes hook hash trust,
nullable Stop answer and PreCompact `continue: false`. [Official App Server documentation](https://learn.chatgpt.com/docs/app-server)
is supplemental; installed schema and parser evidence control compatibility decisions.

## Gate CRG-0001

Capability discovery can pass with explicit safe degradation. Foundation tests and unchanged
production behavior must independently pass. See IMPLEMENTATION_STATUS.md for gate results.
'''
