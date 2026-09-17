
## Normalized analytics (implemented, offline/local only)

The legacy `ledger-import` path remains compatible. New normalized v1 observations
use a separate canonical store; they do not certify undocumented native schemas.
Create JSONL records using [the contract](architecture/telemetry-contract.md), then:

```sh
python -m crg analytics-import --database ./private/analytics.sqlite --input ./input/observations.jsonl --authorized-root ./input --session example --runtime-version verified-adapter-version
python -m crg analytics-status --database ./private/analytics.sqlite --at 2026-09-18T00:00:00Z --timezone Australia/Melbourne --format human
python -m crg analytics-status --database ./private/analytics.sqlite --at 2026-09-18T00:00:00Z --window rolling_168h --format json
python -m crg export-preview --database ./private/analytics.sqlite
```

Commands consume bounded complete records; repeat explicit imports while `lag_bytes`
is nonzero. `--bootstrap-at-end` explicitly excludes historical records and requires
a complete newline boundary. Rotation/truncation fails for revalidation instead of
silently mixing generations. A real native adapter must separately establish its
schema and current-runtime binding; the bundled default reads normalized records.

Context, local usage, account activity and quota remain separate. Account activity
is `UNSUPPORTED` until an official authorized contract is verified. Unknown values
are null/UNKNOWN. Calendar weeks use Monday boundaries in the selected timezone;
rolling windows are exactly 168 hours. See [privacy](privacy.md) before export.
No command installs a global hook, switches models or redeems credits.

Confirmed task forecasts use `forecast-next --database PATH --intent INTENT.json
--policy POLICY.json --at ISO_TIMESTAMP --target wall_ms`, followed by
`forecast-outcome --database PATH --input OUTCOME.json`. Intent contains a confirmed
task ID, kind/risk, target files, acceptance list and numeric features; policy fixes
model, effort, runtime, service tier, single-agent mode and tool family. The ledger
stores only projected hashes/counts. See `crg/features.py` for the v1 closed contract.
`task-capacity --input EVIDENCE.json` accepts only explicitly supplied quota/task
attribution; it does not refresh an account or redeem anything. These commands run
without an LLM. Undefined intent and uncalibrated cohorts return null estimates.
