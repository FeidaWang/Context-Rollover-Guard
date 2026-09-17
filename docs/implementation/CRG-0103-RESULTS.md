# CRG-0103 — Runtime paths and diagnostic states

Baseline re-read: local main `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`, unchanged from the supplied audit. The uncommitted CRG-0101/0102 work is preserved. Remote-main freshness is not claimed.

## Contract and usage

Use Python 3.11+ (replace `python3.13` below with your supported interpreter).

```sh
python3.13 -m crg init --workspace /path/to/project
python3.13 -m crg doctor --workspace /path/to/project
python3.13 -m crg doctor --workspace /path/to/project --format human
```

`init` creates only a private `crg.toml` with guarding and emergency blocking disabled. The workspace must exist. Existing files and symlinks are refused; nothing is overwritten. It does not install hooks, create sessions, create runtime storage, or invoke Codex. For a project with existing configuration, edit that configuration directly.

Ordinary `doctor` is read-only and launches no process. JSON is the default; `--format human` gives concise text. The old doctor result shape is replaced by explicit dimensions, without a single `production_enabled` status:

| Field | Meaning |
|---|---|
| configured | At least one CRG field came from user/repo/CLI configuration |
| runtime_available | Selected binary is executable/discoverable locally; not a successful RPC or authentication claim |
| schema_verified | Cached manifest's complete hash list and request schema validated, with binary-path binding; does not verify the currently installed version |
| hooks_discovered | Nonempty workspace `.codex/hooks.json` definitions found; not CRG ownership or trust |
| hooks_trusted | `null`: no fresh, CRG-bound trust readback in this command |
| telemetry_available | `null`: schema support and cached observations do not prove a current stream |
| guard_enabled | Effective configuration value |
| guard_active_for_session | `false` when disabled; otherwise `null`, because this command does not own a verified live session |

JSON `null` appears as `UNKNOWN` in human output. Cached receipt time/version/errors are exposed separately. MODE_A/B/C remain accepted; doctor emits a migration warning without changing their meaning. Missing or malformed evidence never grants activation.

## Locations

All keys belong to `[context_rollover]`, with existing default/user/repo/CLI precedence. Relative paths are anchored to the selected workspace, never the installed package directory. Path resolution itself creates nothing.

| Config key | Default |
|---|---|
| state_root | `$CODEX_HOME/context-rollover`, or `~/.codex/context-rollover`; repository sample still explicitly selects `.crg-state` |
| archive_root | `.codex/context-archive` |
| schema_cache | `<state_root>/runtime/schema` |
| capability_receipt | `<state_root>/runtime/capabilities.json` |
| hook_receipts | `<state_root>/hooks` |
| evidence_exports | Empty / disabled |

`doctor --probe` explicitly invokes the existing isolated capability probe and writes private schema/receipt files at these paths. It is not run as part of ordinary diagnosis. Reports are exported only if `evidence_exports` is explicitly set. Probe writes use private directories and atomic file replacement; interrupted or mismatched bundles fail subsequent integrity checks.

`install-hooks --apply --workspace ...` defaults to `hook_receipts` for rollback receipts; `--receipt-root` still overrides it. Merely running `init` or `doctor` does not invoke the installer. Owned chat expects its independently reviewed `mode-b-runtime-review.json` inside `hook_receipts`; an installation receipt alone never proves trust.

## Migration

Existing ignored evidence is not silently discovered or moved. To keep using an existing cache, explicitly configure `schema_cache` and `capability_receipt`, and set `hook_receipts` to the directory holding the reviewed hook definitions. Retain the original files until the configured integration has been verified.

`doctor --evidence /existing/evidence` remains an explicit compatibility override for `<evidence>/schema` and `<evidence>/capabilities.json`. Chat/recover `--schema` remains supported and uses the adjacent manifest as before; without it they use both configured paths. No implicit lookup under `docs/context-rollover/evidence` remains in runtime consumers.

## Acceptance and scope

- [x] Six explicit runtime locations, including optional exports.
- [x] Config, probe, repo hook, owned chat, recovery, and hook receipt defaults use the shared resolver.
- [x] Eight distinct diagnostic dimensions with conservative unknowns.
- [x] JSON and human-readable output.
- [x] Safe, non-overwriting initialization.
- [x] Regression tests for paths, inert reads, missing/corrupt metadata, cached-versus-active distinction, private probe outputs, and explicit overrides.
- [x] English/Chinese usage and migration documentation.

Live runtime/session verification remains pending. No live probe, hook installation, model request, or active-task mutation was performed during implementation. Diagnostics intentionally leave live trust/telemetry/session activation unknown instead of inferring them from historical receipts. Capability discovery expansion remains CRG-0105; release artifact unification remains CRG-0104.

## Validation — OFFLINE_TEST

`python3.13 scripts/verify_offline.py --clean` passed on local macOS/Python 3.13.14 in a temporary clean committed snapshot with private evidence absent, isolated user configuration, and network/live-runtime audit guards enabled:

- 176 unit tests passed (13 new CRG-0103 tests).
- 2 offline CLI integration tests passed.
- Freshly built pyz self-test in a staged skill: PASS.
- `git diff --check`: passed.

Remote CI/Linux/Python 3.11–3.12 and real runtime activation remain unverified in this session. Committed distribution archives remain unchanged, pending CRG-0104. No substantive ticket deviation; `init` behavior is conservatively defined by the roadmap's “RuntimePaths, init, doctor” deliverable. Work is retained as local reviewable changes; no PR/release was published.
