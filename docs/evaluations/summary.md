# Offline evaluation and evidence boundaries

Reproduce with `python3.13 scripts/benchmark_continuity.py --output /tmp/crg-continuity.json`
and `python3.13 benchmarks/local_ingest.py`. The checked-in
[continuity result](continuity.json) contains all four synthetic protocol cases,
source hashes, fixture hash, elapsed time, exact prompt checks and duplicate mutation
counts. Each arm creates an independent temporary workspace/client. Native-only,
native-plus-observation and requested fresh recovery use the same synthetic protocol
contract. They are protocol arms, not real model workload comparisons.

[Local reader measurements](local-ingest.json) separate process import startup,
initial binding and hot callbacks, with bytes read for a 100 MiB sparse history.
Hardware architecture, Python, OS, sample size and cache limitations are recorded.
These measurements do not establish a universal 100 ms SLA or live token savings.

Live tokens, quality, human intervention, actual native compaction and real-world
adoption remain unknown. No savings percentage is calculated. The independent unit
for future comparison is a task/project, never repeated events from one task.
Volunteer trials: zero recruited/observed in this evaluation. Negative protocol
results must remain in the output; do not filter failures from reports.

## Separately authorized live protocol (not run)

Before a pilot, fix the exact repository revision, isolated starting checkout,
task acceptance commands, model/effort/runtime/service/tool/permission tuple,
native feature status and explicit financial/request ceiling. Run matched tasks
in native-only, cooperative and separately requested recovery arms. Record all
attempts, repairs, refusals, failed acceptance, complete workflow usage, elapsed
and human-wait time, overhead and missing data. Stop at the budget or any uncertain
mutation; never replay it to obtain a favorable result. Obtain contributor consent
before sharing sanitized aggregates. Public statements must name denominator,
coverage, versions and negative outcomes. No participant or live pass is implied.
