# Metric and estimate contracts

These are local observations, not complete account billing. Unknown values are `null`; zero is used only when explicitly observed or a count of recorded items is genuinely zero.

| Metric | Scope / source | Time basis | Reset behavior | Unknown / uncertainty |
|---|---|---|---|---|
| `known_total_tokens` | Explicit `source_scope`, projected local events; active context excluded | UTC `observed_at` in half-open requested interval | Cumulative decreases start an unknown baseline; historical rows remain | Null without known counters; known/unknown sample counts and partial coverage shown |
| Counter components | Input/output/cache/reasoning fields supplied by source | Same source event | Per-counter deltas only within account/workspace/thread/model partition | Components may overlap; never sum blindly into consumption |
| `active_context_tokens` | Source thread's active-context observation | Individual event time | No consumption aggregation | Null without an authoritative active-context field |
| Remaining percentage | Supplied account fingerprint + bucket snapshot | Observation time, caller freshness TTL, caller query time | Authoritative reset event; crossed reset boundary and at least 10-point drop; or explicit user confirmation create an epoch | Stale current value is null; historical observed value stays labeled historical; never a token balance |
| Quota epoch | Same account and bucket; source reset/readback evidence or declared confirmation | UTC event boundary | Immutable chain, no deletion of local consumption | Confidence `SOURCE_CONFIRMED`, `INFERRED`, or `USER_CONFIRMED`; declarations are not independent verification |
| Duration estimate | Completed observations, matching runtime; task/model/effort then broader backoff | Latest 200 completed rows, at most 30 days, strictly before prediction | New runtime version uses a cold estimate; old observations retained | At least 5 samples; empirical interval with count/confidence; no coverage guarantee |
| Duration EWMA | Same completed window, log-duration transform | Oldest-to-newest within selected window | Recomputed from bounded retained observations | Null for insufficient data; no censored point-duration training |
| Token estimate | Known completed-observation token totals | Same bounded selection as duration | Runtime version backoff remains separate | Median/P90 only with at least 5 known samples; separate token sample count |
| Drift indicator | Recent 5 durations compared with older selected durations | Selected bounded window | Ratio outside 0.5–2 widens empirical interval | Heuristic, not statistical significance or calibrated probability |
| Quality history | Explicit success labels for observed selected configuration | Latest 200 labeled rows, at most 30 days, same runtime | Runtime changes separate histories | Unchosen configurations have no outcomes; completion alone is not a quality label |
| Advice quality rule | Operator-approved candidate risk categories and observed labels | Fresh catalog (at most 1 hour), history (at most 30 days) | Stale data ignored | Beta(1,1) smoothing used only as a rule; quality rejection starts at 10 labels; low sample recommendations remain low confidence |
| Cost rank | Operator-provided ordinal policy | Policy file loaded per request | Operator updates explicitly | Not a price, billing result, or universal cost ranking; unknown ranks exclude candidates |
| Advice confidence | Freshness, policy, local sample support | Current recommendation | Missing inputs return no selection | Qualitative, uncalibrated; never an automatic switch |
| Benchmark elapsed | Local synthetic protocol fixture execution | Monotonic clock per case | Each case measured independently | Not a model latency or production speed claim; real model usage/task correctness/compaction remain null |

The SQLite ledger, quota, and estimate commands only run when explicitly invoked. They do not autonomously collect data, redeem credits, spend funds, or install a background agent. Local computation/storage and explicit runtime reads still have real costs.
