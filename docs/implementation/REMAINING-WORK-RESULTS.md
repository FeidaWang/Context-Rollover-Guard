# Remaining implementation batch — 2026-09-17

Work proceeded in ticket order from CRG-0105 through CRG-0208. Local main was re-read at each ticket boundary and remained `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`; new modules had no baseline counterpart. Earlier uncommitted ticket changes were retained. Remote-main freshness is not claimed.

## Implementation status

| Ticket | Delivered | Evidence / remaining gate |
|---|---|---|
| CRG-0105 | Version-bound schema plus bounded model catalog projection; unknown capabilities remain unknown; no name-based inference | Offline catalog pagination/drift tests pass; real catalog validation pending |
| CRG-0106 | Native-first input routing and independent policy; explicit fresh selection; quiet-point-gated archival | Native pressure, unknown/active child activity, disabled archival, and duplicate safety tested; real activity adapter retains sources because completeness is unavailable |
| CRG-0107 | Version-2 relative/hash-bound handoff pointers, instruction-source replay restrictions, fixed recovery instructions | Injection test and prior archive safety suite pass; only escaped JSON data pointer reaches the new thread, never archive instruction text; inherited system/developer content is unexported/unknown |
| CRG-0201 | SQLite projected event ledger, deterministic dedup, raw cumulative observations and reset-aware deltas; CLI import/report | Replay/conflict/order/concurrent-writer/unknown/future-schema tests pass; automatic capture is intentionally absent |
| CRG-0202 | Scoped snapshot imports, retained epochs, freshness/status CLI | Timezone/reset/account/bucket/unknown cases pass; supplied provenance only, live official readback pending |
| CRG-0203 | Capability and explicit safety-policy filter, configured cost/capability ranks, bounded quality history and optional advice | No name/rank guesses or model switching; stale/invalid evidence returns no selection; monetary cost measurements are unavailable |
| CRG-0204 | Durable pre-task predictions and completed/censored observations; backoff, EWMA, empirical intervals, token quantiles and simple drift | Pre-result immutability, censoring, runtime/staleness, scoring and drift tests pass; real calibration data absent |
| CRG-0205 | Separate status renderer and optional owned-client display | Answer bytes remain untouched; advice failure cannot invalidate the completed answer; no additional inference |
| CRG-0206 | Four-path reproducible synthetic protocol benchmark, all-results manifest | Synthetic protocol checks pass; live baseline task quality/cost/compaction comparison pending |
| CRG-0207 | Contributor quickstart, install/revert, fixture privacy, issue template and compatibility matrix | Local reproductions pass; external maintainer report pending |
| CRG-0208 | Project/evidence/budget/maintenance/application documents | Draft only; public release/CI/evidence URLs, current application-term check, independent report and measured pilot budget still required |

Implementations and offline checks are not equivalent to release-gate completion. M2/M3 still lack real observations and externally reproducible evidence.

## Original deferral gates (superseded for offline preparation only)

The subsequent explicit request to begin CRG-0301–0401 produced [offline preparatory work and its acceptance report](CRG-0301-0401-RESULTS.md). The real-data/runtime/platform gates below still apply to production activation and release acceptance.

The supplied roadmap explicitly gates M4 on sufficient M2/M3 data. The benchmark is synthetic and must not be relabeled as real quality/cost history.

| Deferred ticket | Missing prerequisite |
|---|---|
| CRG-0301 — advanced quality-constrained selection | Enough real, explicit quality/cost observations and time-split baseline evaluation; no fabricated counterfactual labels |
| CRG-0302 — calibrated coverage/drift methods | Real prediction/outcome pairs across runtime/task groups and calibration evaluation |
| CRG-0303 — reset redemption | M4 data gate plus a verified runtime redemption/readback contract; any actual redemption also requires explicit per-action user approval |
| CRG-0304 — attachments/Windows | Stated real demand, exactness/safety fixtures, and platform execution evidence |
| CRG-0401 — future model-family adapter | Official/runtime availability and exposed schema/capabilities; never invent a model ID |

No reset/redemption, model switching, background service, Desktop takeover, external message, application submission, release publication, or live model request was performed. The remaining items require evidence or demand specified by the roadmap before implementation.

## Defined implementation limits / deviations

- Account snapshots use explicit projected import rather than an unverified live account API. Source confidence is preserved as supplied, not independently certified.
- Cost selection uses explicitly configured ordinal cost ranks, with local quality/token/duration summaries, rather than invented current prices. Real monetary optimization remains unsupported.
- Full instructions from the active system/developer stack are not available to the runtime. The manifest records unknown/non-replayable provenance; it never invents hashes or elevates archived content.
- Source archival remains conservative on the real adapter until a complete fresh tool/child observation is available. An accepted handoff can commit with the source retained.
- A fixed one-hour catalog freshness limit, 30-day/200-row estimate window, five-sample minimum, and ten-label quality rule are initial documented policies, not calibrated guarantees. See [metric contracts](../metrics/CONTRACTS.md).
- The OSS application remains unsubmitted and not ready for submission. Local work is not public adoption evidence.

## Validation record

Every ticket's offline gate was run before proceeding to the next. Interim unit counts were 189 (0105), 192 (0106), 193 (0107), 196 (0201), 199 (0202), 202 (0203), 205 (0204), 206 (0205), and 207 (0206/0207), each followed by CLI integration, unified build verification, skill self-test and extracted-ZIP self-test.

The final validation includes further boundary tests and a CLI workflow covering ledger import/dedup/report, quota import/freshness, durable pre-task prediction/completion, history-based advice, and separate rendering. Final counts and build/benchmark receipts are recorded below after execution.


Installed-runtime schema inspection additionally passed using PATH's `codex-cli 0.139.0`, an isolated empty HOME/CODEX_HOME, and `generate-json-schema --experimental`. `model/list` empty parameters validate against that generated schema. Its service-tier objects use an `id` field, now covered by normalization tests. See the [sanitized receipt](../compatibility/schema-0.139.0.json). This does not query an account, start a thread, run a model, or prove live catalog/authentication support. PATH resolves to a different version than the historical native transcript fixture (0.153.4); those evidence scopes remain separate.

### Final measured result — OFFLINE_TEST

- Clean temporary checkout: **210 unit tests + 3 CLI integration tests passed** on macOS/Python 3.13.14.
- Unified build, both manifests, and **10 artifact hashes** verified.
- Bundled-skill and extracted-ZIP self-tests passed.
- All **4 synthetic benchmark paths** passed; real task quality/model cost/compaction metrics remain null in [the result manifest](../benchmarks/latest.json).
- Working-tree distribution artifacts were rebuilt and reverified against source fingerprint `ff6037cfcd0a634f9479a69da45d9b670000d1d4a2cba73fb3e0408f7fbc78a4`.
- Package version remains `0.1.0`; the local build accurately records baseline commit plus `source_dirty: true`. Nothing was published or submitted.
- `git diff --check` passed. Remote CI and independent/live validation remain pending as listed above.
