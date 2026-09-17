# CRG-0301–0401 implementation and acceptance — 2026-09-17

## Decision

**Offline preparatory implementation accepted; M4/M5 production/release acceptance remains blocked. CRG-0304 remains deferred.** This is not a claim that all five tickets meet their original exit criteria.

The explicit request to start this batch advances development beyond the previous deferral, while retaining the roadmap's real-data and runtime/platform acceptance requirements. Earlier uncommitted work was preserved. Baseline HEAD is `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`; remote freshness is not claimed.

| Ticket | Delivered and locally tested | Remaining acceptance requirement |
|---|---|---|
| CRG-0301 | Offline time-split evaluator, factual chosen outcomes only, Wilson quality bound, measured-cost ranking, optional p80 latency constraint, sparse/incomplete-data fallback | Real sufficient observations, current capability/safety filter at activation, bias-aware baseline comparison showing improvement without reduced safety; hierarchical sparse-cell methods not delivered |
| CRG-0302 | Per-context/action/day duration/token coverage, rolling misses and residual drift, training-only empirical interval widening with held-out baseline comparison | Real calibration evaluation, tuned thresholds and integration into production estimates; no mathematical coverage guarantee |
| CRG-0303 | Private durable intent/approval binding, pre-submit claim, concurrency exclusion, receipt persistence, keyed read-only reconciliation | Verified production adapter, atomic account/effect/cost binding, exact approval UI and live readback contract; no actual redemption performed |
| CRG-0304 | Source/platform gap assessment and concrete acceptance checklist | Attachment transport and exactness fixtures, Windows persistence adapter and actual Windows execution; implementation deferred |
| CRG-0401 | Exact runtime-discovered model/effort resolution, freshness/uniqueness checks, metadata revision invalidation and unknown preservation | Live verified availability/schema for any particular new family; no future model ID or capability is guessed |

The [experimental contracts](../metrics/EXPERIMENTAL-M4.md) document input schemas, policy constants, adapter interfaces, examples and limits. Ordinary advice, prediction, chat and default configuration remain unchanged. No production reset adapter, model switch, background job, external submission or published release was added.

## Validation

- Clean temporary Git snapshot: **236 unit tests and 4 CLI integration tests passed**, macOS/Python 3.13.14, with isolated HOME/CODEX_HOME and network/live-runtime guards.
- Added 26 unit tests and one CLI integration test relative to the preceding 210/3 baseline. Coverage includes factual-only outcomes, duplicate/conflicting tasks, held-out leakage, missing costs/censoring, context separation, cross-day misses, training-only corrections, approval expiry/binding, concurrent submission, receipt loss/reopen, pre-submit crash, account/contract changes, pending-intent exclusion and model metadata drift.
- Unified build and both manifests passed; **10 artifact hashes verified**. Bundled-skill and extracted-ZIP self-tests passed.
- All **4 synthetic continuity benchmark paths passed**; [full result manifest](../benchmarks/latest.json) retains real task quality, model consumption and live compaction as unknown.
- Working-tree distribution rebuilt and verified against source fingerprint `023edd4dfebb60c117e012a16f9f825c4ea69a8fb69a84a7b36eaf5571e3b65a`, version `0.1.0`, baseline commit plus `source_dirty: true`.
- `git diff --check` passed. No remote CI, Windows execution, live model request, reset redemption, release publication or external submission was performed.
- The first focused invocation used the system Python 3.9 (below the declared minimum) and exposed a test-temp-path symlink issue. The fixture now uses a resolved temporary path; the final suite ran on supported Python 3.13.14. Persistence symlink protections were not relaxed.

## Closeout boundary

This batch is locally packaged and documented, not released. Real quality/cost data cannot be fabricated from protocol fixtures; a generic synthetic model ID cannot establish future availability; a macOS run cannot establish Windows compatibility. Until those prerequisites exist, the original tickets remain open for production acceptance. This report supersedes the earlier blanket implementation deferral only for the offline scope above.
