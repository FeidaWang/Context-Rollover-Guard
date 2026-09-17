# Evidence inventory — 2026-09-17

This is a readiness inventory, not a record of adoption or an eligibility claim.

| Claim | Evidence | Limitation / publication requirement |
|---|---|---|
| Offline verification is reproducible | `python3 scripts/verify_offline.py --clean`; [CI definition](../../.github/workflows/offline.yml) | Local macOS execution observed; remote job links not available |
| All defined synthetic continuity cases are retained | [benchmark artifact](../benchmarks/latest.json), [methodology](../benchmarks/README.md), [fixture definitions](../../tests/fixtures/continuity-benchmark.json) | Synthetic protocol results only; not live task quality/cost evidence |
| Distribution integrity is checked | [builder/verifier](../../scripts/build_release.py), manifests in `dist/` | Local artifacts; release permalink pending |
| Recovery rejects blind replay | Unit tests and [security boundaries](../../SECURITY.md) | Link the published source commit/CI run before application submission |
| Account data has explicit scope/freshness | Quota import/status implementation | Supplied source provenance; live account readback not verified |
| External maintainer success | UNKNOWN | Need an independently reproducible, consented public report |
| Real-world adoption/downloads/stars | UNKNOWN | No measurements collected; no quantitative adoption claim permitted |
| ETA or recommendation effectiveness | UNKNOWN | Need real completed observations and time-split evaluation |

Do not paste local test totals into an application as public release evidence. Publish the source and benchmark/CI artifacts first, then replace pending entries with immutable public URLs. Retain failures. Public exports must exclude prompts, answers, credentials, account identifiers, and private journals.
