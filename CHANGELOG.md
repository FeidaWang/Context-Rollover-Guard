# Unreleased

## CRG-0101

- Repository defaults now disable guarding and emergency blocking, with PATH-based runtime discovery instead of a machine-specific binary.
- `config` includes per-field provenance and an inspection-only `--codex` override; existing value sections remain compatible.
- Import/config reads and disabled hook dispatch are covered by offline side-effect regression tests.
- Baseline: main `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`, unchanged at ticket start. Five focused acceptance tests pass on Python 3.13 (OFFLINE_TEST). Full clean-checkout gate follows CRG-0102 because baseline tests require ignored evidence. Live activation and Windows support remain unverified. No state-machine changes.

## CRG-0102

- Offline schema/compaction tests now use committed, minimal synthetic fixtures instead of ignored author-machine evidence. Repo-hook tests also inject synthetic version evidence and check missing-evidence UNKNOWN behavior.
- Added clean-checkout verification and a Linux/macOS Python 3.11/3.12/3.13 CI matrix. Verification isolates user settings, blocks network/live runtime launches, runs CLI integration tests, and self-tests freshly built pyz bytes in a staged skill.
- Live generated-schema inspection is separate and opt-in; synthetic fixtures do not establish runtime compatibility.
- Baseline re-read before implementation: main `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`, unchanged. Runtime path restructuring and unified release artifacts remain CRG-0103/0104 scope.

Combined gate: 163 unit tests, 2 CLI integration tests, and the freshly built staged pyz self-test passed on a temporary clean Git checkout (macOS, Python 3.13.14; OFFLINE_TEST). Remote CI and live runtime validation are pending. See [first-batch results](docs/implementation/FIRST-BATCH-RESULTS.md) for acceptance checks and scope boundaries.

## CRG-0103

- Introduced lazy `RuntimePaths` resolution for state, archives, schemas, capability receipts, hook receipts, and optional exports; runtime consumers no longer assume a source-tree evidence directory.
- Added non-overwriting, disabled-by-default `init`. Ordinary `doctor` is read-only, with JSON/human formats and eight independent status dimensions. Cached evidence never establishes live trust, telemetry, or session activation.
- Kept explicit `--evidence`, `--schema`, and `--receipt-root` overrides. Existing integrations must configure legacy paths explicitly; old MODE names still parse and produce a doctor-only migration warning.
- Capability probes now write private, atomic artifacts at resolved paths; report export is opt-in. No unified release build or active-session switching was added.
- CRG-0103 clean-snapshot validation: 176 unit tests, 2 CLI integration tests, and fresh pyz self-test passed on macOS/Python 3.13.14. Live verification and remote CI remain pending; details in [CRG-0103 results](docs/implementation/CRG-0103-RESULTS.md).

## CRG-0104

- Added one stdlib-only release builder for recursive package contents, both identical pyz copies, complete skill ZIP, build metadata, and matching manifests. The old build entry point delegates to it.
- Added `--verify` for source/artifact hashes, package versions, metadata, and ZIP/directory agreement. Manifest layout is now `format_version: 1`, with dist-relative hashes under `artifacts`.
- Portable Python 3 shebang and skill examples require any supported Python 3.11+ interpreter. Fixed `SOURCE_DATE_EPOCH` and unchanged inputs/provenance produce identical bytes; archives use uncompressed members for reproducibility.
- Clean-snapshot validation passed: 185 unit tests, 2 CLI integration tests, artifact verification, and both skill/ZIP self-tests on macOS/Python 3.13.14. Details and interruption boundaries: [CRG-0104 results](docs/implementation/CRG-0104-RESULTS.md).

## CRG-0105

- Explicit schema probes now optionally query the schema-advertised `model/list` catalog with bounded pagination. Catalog projections retain unknown fields, never derive efforts or context windows from names, and reject incomplete catalogs as recommendation inputs.
- Removed invalid-parameter mutation-method probes; isolated discovery sends read-only requests only. Catalog receipts remain bound to the generated schema/runtime receipt. Live runtime verification remains pending.

## CRG-0106

- Separated continuity policy from transaction state. Owned chat retains native continuation under pressure; migration now requires a per-input `fresh: true` selection. Existing explicit emergency blocking configuration remains supported.
- Source archival requires a fresh adapter activity read with complete terminal/detached tools and children. Missing observation preserves the source and commits the accepted target without replay. The real adapter currently supplies no complete activity proof, so it conservatively retains sources.

## CRG-0107

- New handoffs use version 2, with relative data pointers, file hashes, and explicit instruction-source replay restrictions. Unavailable system/developer text remains unexported and unknown. Existing version-1 archives retain their reconstruction/verification path.
- Thread creation uses fixed trusted recovery instructions; archived handoff text never enters developer instructions. Exact current user text remains the forwarded request; archive pointers remain in the durable prepared journal and an escaped, explicitly untrusted data-location JSON for the target; archive bodies are never promoted.

## CRG-0201

- Added explicit `ledger-import` and scoped `usage` commands backed by private SQLite/WAL storage. The ledger accepts only projected fields, deduplicates source identities, detects conflicting replays, and preserves raw cumulative observations separately from derived deltas.
- Initial/reset baselines and missing counters remain unknown. Active-context samples never enter consumption totals; reporting includes scope, observed UTC interval, source, reset semantics, sample coverage, and unknown counts. No background collector or model request is added.

## CRG-0202

- Added projected account snapshot imports and account/bucket quota epochs, separate from token consumption. Reset evidence follows authoritative-ID, crossed-boundary plus material drop (10 percentage points), then explicit user-confirmation order; history is never deleted.
- `quota-status` exposes source, observation time, freshness, and unknowns; percentages are never converted into token balances. Imports preserve declared provenance; live account integration/readback remains unverified and no redemption is performed.

## CRG-0203

- Added `advise`: runtime availability/effort filtering, explicit operator safety approvals, quality-label filtering, cold-start capability ranking, and configured ordinal cost ranking. Names never imply model capabilities; missing policy/catalog evidence yields no selection.
- Advice reports alternatives, reasons, confidence, samples, source freshness, and zero additional inference calls. Cost ranks are user-supplied policy, not fabricated prices; expired quality observations are ignored. No automatic model switching is performed.

## CRG-0204

- Added durable pre-task `predict` and explicit `complete-observation` commands. Estimates use bounded completed-history windows, task/model/effort backoff, empirical duration intervals, log-duration EWMA, token quantiles, and a simple drift widening rule.
- Runtime changes/stale history return unknown, censoring excludes timeout/cancel/interruption durations from completion estimates, and explicit quality labels feed advice. Predictions precede observations and are immutable; errors/interval hits are scored only after completion. Intervals are uncalibrated empirical ranges, not guarantees.

## CRG-0205

- Added compact independent advice status rendering (`advise --format status`) with empirical ETA, confidence and sample counts. Unknowns stay explicit; no extra inference is performed.
- Owned clients can display precomputed advice after the unchanged answer via `--advice-file`; renderer failures cannot invalidate a completed turn or alter archived answer bytes.

## CRG-0206

- Added deterministic fixture IDs and a four-path continuity benchmark with per-case results, source/fixture fingerprints, measured fixture elapsed time, exact-request and duplicate-mutation checks, recovery, and source-retention outcomes. Failures are retained and cause nonzero exit.
- Real task correctness, model consumption, and live compaction remain explicitly unknown; synthetic results are not cost/quality training data. Live baseline comparison remains an open release gate.

## CRG-0207

- Added contributor quickstart, installation/revert instructions, compatibility-report issue template, explicit data/advice command examples, privacy boundaries, and an evidence-scoped compatibility matrix. One-command offline verification and fixture guidance are linked throughout.
- Independent maintainer reproduction is still pending; no adoption or cross-platform success is invented.

## CRG-0208

- Added project summary, evidence inventory, bounded pilot-credit methodology, maintenance plan, and an unsubmitted OSS application draft. Public release/CI links, independent maintainer reports, live benchmark outcomes, program-term checks, and measured credit amounts are explicitly pending.
- No adoption metrics, eligibility guarantees, prices, or successful application outcomes are fabricated.

Final schema inspection: installed CLI 0.139.0 generated schema and `model/list` parameter validation passed in an isolated environment, without account/model/thread requests. Runtime-reported service-tier object IDs are normalized; real catalog/activation verification remains pending.

Final remaining-batch validation: 210 unit tests, 3 CLI integration tests, 4 synthetic benchmark scenarios, unified artifact verification, and both skill/ZIP self-tests passed. Local artifacts rebuilt; deferred data/demand/runtime gates and implementation limits are recorded in [remaining-work results](docs/implementation/REMAINING-WORK-RESULTS.md).


## CRG-0301–0401 offline preparation

- Added `statistical-audit` with strict projected factual observations, time-split quality/cost selection experiments, sparse-data fallback, grouped coverage/drift and training-only interval widening evaluated against unchanged held-out intervals. No production policy is enabled or baseline superiority claimed.
- Added the injected-adapter reset transaction engine: exact intent/approval binding, durable pre-submit claim, same-account pending exclusion and receipt/readback reconciliation without resubmission. No production endpoint or spending CLI is shipped.
- Added `resolve-model` for fresh exact runtime IDs/efforts and metadata revision invalidation; no model-name capability inference or automatic switch.
- CRG-0304 remains deferred with an explicit attachment/Windows acceptance checklist. Real-data, live-contract and platform gates remain open; see [batch acceptance](docs/implementation/CRG-0301-0401-RESULTS.md) and [contracts](docs/metrics/EXPERIMENTAL-M4.md).
