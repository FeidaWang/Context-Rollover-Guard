# Normalized analytical contracts (v1)

`crg.events.Observation` separates context gauges, usage observations, quota,
timing, outcomes, predictions and optional monetary cost. Unknown is null.
`project` is the adapter's content-dropping boundary; strict constructors reject
cross-object and unknown fields. No transcript is stored in analytics. Scope,
source/version, identity, source time, receipt time, revision and evidence quality
are explicit. Synthetic fixtures do not establish a live adapter contract.

Verified input/output subset semantics add input+output exactly once. Unverified
subsets are never added to a provider total. Unknown scope, unknown aggregation,
parent-including-child totals and child records are excluded from exact totals;
this conservative exclusion can undercount and is disclosed as partial coverage.

`CanonicalLedger` adds versioned tables without changing legacy ledger/recovery
schemas. Both source observation and logical fact/revision identities are durable.
Late revisions and ordered late records rederive only the affected fact and its
immediate successor using indexed series queries. Receipt time is not a revision.
First cumulative observations remain left-censored; decreases remain unknown
corrections. Counter generation changes do not erase usage history. Same-time
snapshots are ambiguous. Account daily buckets never enter local usage totals.

Observation batches and compare-and-swap cursors commit together under SQLite
WAL/FULL transactions. Conflicts roll back, retries deduplicate, future schema and
corruption fail closed. Analytics failures do not mutate the recovery StateStore.
Supported storage is local POSIX disk; native Windows and network filesystems
require separate durability evidence. Legacy imports remain legacy-only and
cannot silently certify normalized observations.
