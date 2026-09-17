# Public offline fixtures

All files here are synthetic and contain no captured prompts, answers, credentials, or account identifiers. They are OFFLINE_TEST inputs, not proof of installed-runtime compatibility or Desktop activation.

- `observe-sequence.jsonl`: four completed turns and a compaction notification.
- `compaction-events.jsonl`: three conversation turns, a separate compaction turn, and another conversation turn; only projected counters, synthetic IDs, and completion markers.
- `protocol/schema/`: a hand-authored minimal schema contract for offline validation and fake stdio servers. It includes only the request fields and capability projections used by these tests, not the complete Codex protocol. It must never be used to authorize live mutations.
- `protocol/capabilities.json`: synthetic provenance and SHA-256 binding for the minimal request schema; the binary is deliberately not a runtime.
- `native-capabilities.json`: synthetic version metadata for the existing 0.153.4 transcript adapter regression; not evidence that a runtime is installed.

When changing a fixture, retain this distinction, keep only necessary fields, use synthetic IDs/counters, and update its hash if applicable. `test_public_fixtures` checks credential-like patterns, projected event fields, and synthetic provenance. Review additions manually too; pattern checks cannot establish privacy on their own.

Live generated schemas are opt-in and separate: `python -m tests.live_schema --schema /path/to/evidence/schema`. This reads existing version-bound evidence; it neither invokes Codex nor proves live activation. Existing `tests/live_*.py` scripts are excluded from offline discovery.

`manifest.json` inventories every public data/schema file with SHA-256, byte size,
synthetic grade, provenance, and direct/transitive consumer paths. It excludes itself
and this README from self-hashing. The default suite checks inventory completeness,
hashes, grades, provenance and consumer path existence; consumer relationships are
also reviewed against source. `continuity-benchmark.json` is the synthetic benchmark
scenario definition, consumed by `scripts/benchmark_continuity.py`.

Default tests resolve these inputs with `tests.support.fixtures.fixture_path`.
FakeClient (including child-process crash tests) and wire tests share that resolver;
missing files fail instead of falling back to private or installed-runtime evidence.
The CLI integration replay uses `observe-sequence.jsonl`, retaining its behavioral
assertions. `SyntheticCompactionRegression` uses `compaction-events.jsonl` and makes
no Desktop runtime claim.

Reproduce the bounded CRG-1002 check from the repository root with
`python3.13 docs/audit/verify_public_fixtures.py`. It runs focused tests followed by
`python3.13 -m unittest discover -s tests/unit -v` and
`python3.13 -m unittest discover -s tests/integration -v` in a disposable source
snapshot with private evidence absent, isolated HOME/CODEX_HOME, an allowlisted
environment and a PATH containing only Python and Git. Its inherited Python audit
guard rejects covered network/runtime launches; OS-level network isolation remains
unverified. No live suite is included or silently skipped.
