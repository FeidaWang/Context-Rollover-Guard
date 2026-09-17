# Public offline fixtures

All files here are synthetic and contain no captured prompts, answers, credentials, or account identifiers. They are OFFLINE_TEST inputs, not proof of installed-runtime compatibility or Desktop activation.

- `observe-sequence.jsonl`: four completed turns and a compaction notification.
- `compaction-events.jsonl`: three conversation turns, a separate compaction turn, and another conversation turn; only projected counters, synthetic IDs, and completion markers.
- `protocol/schema/`: a hand-authored minimal schema contract for offline validation and fake stdio servers. It includes only the request fields and capability projections used by these tests, not the complete Codex protocol. It must never be used to authorize live mutations.
- `protocol/capabilities.json`: synthetic provenance and SHA-256 binding for the minimal request schema; the binary is deliberately not a runtime.
- `native-capabilities.json`: synthetic version metadata for the existing 0.153.4 transcript adapter regression; not evidence that a runtime is installed.

When changing a fixture, retain this distinction, keep only necessary fields, use synthetic IDs/counters, and update its hash if applicable. `test_public_fixtures` checks credential-like patterns, projected event fields, and synthetic provenance. Review additions manually too; pattern checks cannot establish privacy on their own.

Live generated schemas are opt-in and separate: `python -m tests.live_schema --schema /path/to/evidence/schema`. This reads existing version-bound evidence; it neither invokes Codex nor proves live activation. Existing `tests/live_*.py` scripts are excluded from offline discovery.
