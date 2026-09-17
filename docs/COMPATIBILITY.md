# Compatibility evidence

Evidence is scoped, not a blanket support claim. Review date: 2026-09-18.

| Surface | Evidence | Status |
|---|---|---|
| macOS / Python 3.11.15, 3.12.13, 3.13.14 | Local clean-snapshot tests and final artifacts with verified OS network denial | OFFLINE_TEST passed; ci-os-macos-3.*-final.json |
| Linux / Python 3.11, 3.12, 3.13 | Current OS-isolated workflow configured; historical run uses old code | Current snapshot not yet verified on Linux |
| Codex CLI 0.139.0 generated schema | [Sanitized schema check](compatibility/schema-0.139.0.json) | OFFLINE_TEST: generation and model/list parameter validation passed; no account or model requests |
| Live Codex model catalog | Schema-gated bounded read adapter | Implemented; live verification pending |
| Live account snapshots | Explicit projected import | Supplied provenance only; no live adapter/readback verified |
| Live tools/children quiet point | Complete fresh activity required | Real adapter observation unavailable; source retained |
| Desktop UI switching | No supported takeover | Not claimed |
| Windows / attachments | No validated adapter | Deferred pending demand and tests |
| Statistical ETA accuracy | Empirical estimator plus offline time-split coverage/recalibration audit | Uncalibrated; production accuracy unknown |
| Reset redemption | Synthetic durable transaction engine tests | No production adapter, host approval UI or live readback verified |
| New model-family resolution | Exact catalog ID/effort and metadata revision checks | Synthetic adapter tests only; no new live family availability claimed |

Old local evidence is never promoted to a current live claim. Add external reports here only after obtaining a reproducible public link and recording the exact source/runtime/environment scope.

## CRG-1009 evidence boundary

The [CI policy](ci-policy.md) defines fail-closed OS network checks and the exact
local command. Local macOS/Python 3.11–3.13 passed OS network isolation and
offline verification; see `docs/audit/ci-os-macos-3.*-final.json`. Historical hosted
[run 35226491499](https://github.com/FeidaWang/Context-Rollover-Guard/actions/runs/35226491499)
passed five jobs and failed Linux 3.13, using an older runner and test snapshot.
Current hosted matrix, fork PR and manual release jobs remain NOT_RUN. The initial
nested sandbox denial is retained as historical evidence; the approved local
process-level sandbox now succeeds without changing global policy.
Native Windows is unsupported/unverified. No new live compatibility badge or
native runtime support is inferred from package or workflow tests.
