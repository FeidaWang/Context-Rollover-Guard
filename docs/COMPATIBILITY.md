# Compatibility evidence

Evidence is scoped, not a blanket support claim. Review date: 2026-09-17.

| Surface | Evidence | Status |
|---|---|---|
| macOS / Python 3.13.14 | Local clean-snapshot unit/integration/build/self-tests | OFFLINE_TEST passed; see implementation results |
| Linux / Python 3.11, 3.12, 3.13 | CI workflow configured | Not executed/observed in this session |
| macOS / Python 3.11, 3.12 | CI workflow configured | Not executed/observed in this session |
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
