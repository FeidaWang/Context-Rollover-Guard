# Contributor quickstart

Use Python 3.11+ and Git on Linux/macOS. No pip dependencies or Codex login are needed for offline verification. Windows is not yet verified; the runtime currently uses POSIX locking/private-file primitives.

## Verify, then install

```sh
python3 --version
python3 scripts/verify_offline.py --clean
python3 scripts/build_release.py
python3 scripts/build_release.py --verify
python3 dist/context-rollover-guard/scripts/self_test.py
```

The clean runner uses a temporary committed snapshot of non-ignored source, isolates user configuration, blocks network/live-runtime launches during verification, builds every artifact, and tests both the skill directory and exported ZIP. It does not change the original checkout's release artifacts. The explicit build command does.

Install `dist/context-rollover-guard` through your skill installer, or copy that directory to a **new, unoccupied** skill directory of your choosing. Do not overwrite a different skill. Record the installation path. Installing the skill does not install hooks or create a background service.

To uninstall a manually copied skill, remove only that recorded copy. For a plugin-managed installation, use that plugin manager's uninstall action. Existing handoff journals remain recovery data; retain them until pending work is reconciled. Do not reset a journal to force a retry.

Hooks are a separate explicit integration. `install-hooks` previews a merge; `--apply` writes it and returns a rollback receipt. To reverse that installation, use:

```sh
python3 -m crg uninstall-hooks --receipt /exact/receipt/directory
```

This removes only receipt-owned entries and preserves later user changes. It does not invent a trusted-hook decision or delete archives. Disable guard configuration (`enabled = false`) when retiring an integration; preserve unconfirmed transaction evidence.

## Inspect safely

For a workspace without CRG configuration:

```sh
python3 -m crg init --workspace /absolute/project
python3 -m crg doctor --workspace /absolute/project --format human
```

Existing configuration is never overwritten. Missing trust/telemetry/session activation stays UNKNOWN. Do not interpret an executable on PATH or a cached schema hash as live activation. `doctor --probe` is a separate explicit runtime probe. It is excluded from offline validation.

For owned chat, `{"text":"..."}` continues the current thread under pressure. `{"text":"...","fresh":true}` explicitly chooses a fresh continuation. Unknown tool/child activity preserves the source. There is no automatic Desktop takeover.

## Usage, advice, and estimates

All collection is explicit and local. Import only projected counters, never a native transcript. Account identifiers must already be replaced by a locally salted fingerprint; do not put credentials or raw account IDs in fixtures.

```sh
python3 -m crg ledger-import --database /private/directory/usage.sqlite --input /projected/events.jsonl
python3 -m crg usage --database /private/directory/usage.sqlite --scope local --start 2026-09-01T00:00:00Z --end 2026-10-01T00:00:00Z
python3 -m crg quota-import --database /private/directory/usage.sqlite --input /projected/quota.jsonl
python3 -m crg predict --database /private/directory/usage.sqlite --task-class maintenance --model ACTUAL_CATALOG_ID --effort ACTUAL_SUPPORTED_EFFORT --runtime-version ACTUAL_VERSION
python3 -m crg complete-observation --database /private/directory/usage.sqlite --input /projected/outcome.json
```

Ledger events require `source_event_id`, timezone-aware `observed_at`, `source_kind`, `source_scope`, `completion_state`, and `counter_semantics` (`per_event`, `cumulative`, or `unknown`). Optional fields are documented by the closed projection in `crg/ledger.py`. Cumulative first/reset observations establish unknown baselines; they are not counted as zero consumption. Cached and reasoning token components can overlap input/output; they are not blindly added together. Active-context pressure is separate.

Quota snapshots require source identity, account fingerprint, bucket, snapshot ID, and observation time. Supply authoritative values only when available. Explicit reset IDs are source evidence, not an instruction to redeem a credit. Stale snapshots do not represent current remaining quota. Percentage-only limits never yield a token balance.

`predict` must run before execution. Save its returned prediction ID. An outcome JSON contains `prediction_id`, `status`, optional `duration_ms`, `total_tokens`, explicit `success` quality label, and optional timezone-aware `at`. Completed observations need a duration; timeout/cancel/interruption/superseded results are censored and cannot label successful quality. Completing work is not automatically a correctness label.

`advise` takes `--catalog` (explicit probe receipt), `--features` and `--policy` JSON. Policy candidates specify actual `model_id`, supported `effort`, `approved_for` risk categories (`state`, `protocol`, `security`, `debug`, `live`), nonnegative ordinal `cost_rank`, and `capability_rank`. These are operator policy, not guessed model-name capabilities or live prices. Optional `--database` plus `--runtime-version` uses local explicit quality labels. Missing/stale inputs produce no recommendation. `--format status --estimate /saved/prediction.json` displays separate advice without changing an answer.

No learning step makes an additional model call. Local computation, storage, and explicit account/runtime reads still have real costs. Current statistics are empirical and uncalibrated; do not claim coverage guarantees or use synthetic tests as production quality observations.

## Good first contributions

- Add one sanitized protocol-drift or timezone-reset fixture.
- Reproduce the offline suite on another supported Python/OS combination.
- Report one unsupported runtime schema with projected fields and exact version.
- Improve a failure message while preserving unknown-outcome behavior.

Follow [fixture guidance](../tests/fixtures/README.md). Never attach raw conversations, authentication files, native private journals, or account IDs to a public issue. A synthetic reproduction is preferable.

Run the [continuity benchmark](benchmarks/README.md) and include failures as well as successes. Compatibility reports are evidence only for their stated runtime, surface, platform, and scope.
