# Continuity benchmark

Run `python3 scripts/benchmark_continuity.py --output docs/benchmarks/latest.json` with Python 3.11+.

Definitions and fixture IDs live in `tests/fixtures/continuity-benchmark.json`. Every attempted case is retained, including failures; the command exits nonzero if any case fails. Recorded hashes identify the actual uncommitted source, rather than treating HEAD as its complete provenance.

The four paths compare native continuation, observation-only policy, explicit handoff, and recovery after accepted forwarding loses its receipt. Inputs are synthetic. Protocol correctness means exact request preservation and zero duplicate mutation. Source retention is verified when child/tool activity is unknown. Elapsed time measures local fixture execution only.

Final real task quality, authoritative model consumption, and live compaction counts are unknown (`null`). This benchmark does not claim CRG beats native continuation in cost, quality, or latency. Those require a preregistered live pilot and public results, including failures. Do not train production quality/cost selection on these synthetic outcomes.
