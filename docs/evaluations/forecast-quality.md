# Local forecast evidence

`python3.13 benchmarks/forecast_replay.py` regenerates the checked-in
[chronological comparison](forecast-replay.json). Constant, last-value and rolling
median baselines are scored on strictly earlier outcomes with MAE, bias, pinball
loss, interval width and observed coverage. Each synthetic project is reported
separately, including heavy tails, drift, recovery and tiny targets. No random
split, real adoption or per-task coverage guarantee is claimed.

Production uses the declared rolling-median baseline. EWMA's base-residual update
is implemented and regression-tested as an experimental pure helper; there is no
evidence justifying activation of a more complex predictor. No RLS, embeddings,
LLM judge or conformal guarantee is enabled. Each target (wall time, active time,
tokens) is separate. Stored forecasts are immutable, corrections revise one
outcome, and only outcomes available before prediction time enter its cohort.

The performance cohort fixes task kind/risk/model/effort/runtime/service/toolset
and execution mode. A quota reset does not erase duration experience. Missing
samples yield null; feature-range drift or sustained score deterioration yields
UNKNOWN, with a recent stable baseline as a visible recovery fallback. Censored
and intervened outcomes remain recorded but cannot become successful regression
labels. Effective sample size equals the unweighted distinct task count; project
independence is not established by that number.

Timing default is submit-to-model-finish, not acceptance time. Separate timing
projection can exclude observed approval intervals and union overlapping tools;
unknown waits remain unknown. A restart without a monotonic bridge is incomplete.

Capacity is conditional on clean per-task percentage-point samples from the same
quota epoch and exact policy. Missing buckets, hidden activity, stale data and
sub-resolution movement yield UNKNOWN. The horizon ends at the earliest known
reset; no fixed subscription token budget is invented.
