# Context Rollover Guard — Technical Implementation Specification

This document is an implementation contract for Codex. Execute tickets in priority order. Preserve the existing safety invariant: **unknown mutation acceptance is recovery work, never retry permission**.

## 1. Architecture target

Split the system into these conceptual layers while keeping dependencies minimal:

```text
Runtime adapter
  -> capability/model discovery
  -> event normalization
  -> continuity policy
  -> durable state/transaction layer
  -> usage/quota ledger
  -> local predictor/advisor
  -> renderer/CLI
```

Do not make the ledger depend on the rollover state machine. Do not make model advice authoritative for execution. Do not make UI rendering part of answer archival.

## 2. Global invariants

All tickets MUST preserve these invariants:

1. Never resend an ambiguously accepted mutation automatically.
2. Never archive the source thread before positive evidence that the target accepted the intended user request and the source is safe to retire.
3. Never substitute cumulative session usage for active-context usage.
4. Never substitute missing usage/quota data with zero.
5. Never elevate archived prompt/answer text into developer authority.
6. Never write global hooks or trust decisions as an import side effect.
7. Never claim a model capability from its name alone.
8. Never delete historical usage because a quota period reset.
9. Never use recommendation failure to block normal task completion.
10. Never require a model call to update local statistics.

## 3. P0 implementation tickets

### CRG-0101 — Safe defaults and platform-neutral configuration

**Objective:** Make a clean checkout inert, portable, and truthful.

**Primary files:** `crg.toml`, `crg/config.py`, `README.md`, `README.zh-CN.md`, tests under `tests/unit/`.

**Implement:**

1. Change repository `crg.toml` to safe example defaults:
   - `enabled = false`
   - `mode = "auto"` or observe-only equivalent
   - no absolute `/Applications/.../codex` path
   - `block_auto_compact = false`
   - `force_rollover_on_next_prompt = false`
2. Treat a user-specific Codex binary path as user-local configuration, not repository policy.
3. Add a config command that prints the resolved source of each important setting (`default`, `user`, `repo`, `cli`) without exposing secrets.
4. Update docs so “install skill” is not described as “install hooks.”
5. Add regression tests proving clone/import/config-read has no hook writes or runtime mutations.

**Acceptance tests:**

- `test_repository_defaults_are_inert`
- `test_import_has_no_filesystem_side_effects`
- `test_config_without_codex_binary_uses_runtime_discovery`
- `test_emergency_blocking_is_opt_in`

**Reject the ticket if:** a clean checkout can block a prompt without an explicit enablement path.

### CRG-0102 — Public fixtures and clean-checkout CI

**Objective:** Remove author-machine evidence from unit-test prerequisites.

**Primary files:** `tests/fixtures/`, `tests/unit/test_appserver.py`, `test_foundation.py`, `test_observe.py`, CI workflow.

**Implement:**

1. Add a committed minimal protocol-schema fixture containing only fields required by offline tests.
2. Add a committed projected compaction event fixture that contains no prompt/answer text.
3. Parameterize tests to use public fixtures by default.
4. Keep live generated schema tests separate and opt in.
5. Add CI for Python 3.11, 3.12, and 3.13 on Linux; add macOS if budget permits.
6. CI MUST run:
   - unit suite;
   - offline CLI integration test;
   - packaged self-test after build;
   - a check that ignored evidence paths are not required.

**Acceptance tests:**

- Create a temporary clean checkout with no `docs/context-rollover/evidence` and run all offline tests.
- Assert no network/model request is made in offline CI.
- Assert fixtures contain no credential-like strings or raw private transcript text.

### CRG-0103 — RuntimePaths and doctor state model

**Objective:** Eliminate hardcoded evidence path assumptions and make state understandable.

**Primary files:** new `crg/runtime_paths.py`, `crg/cli.py`, `crg/capability_probe.py`, `crg/repo_hook.py`, `crg/owned_client.py`.

**Implement:**

Define `RuntimePaths` with explicit locations for:

- CRG state root;
- archive root;
- generated runtime schema cache;
- capability receipts;
- hook installation receipts;
- optional benchmark/evidence exports.

Add status dimensions:

```text
configured: bool
runtime_available: bool
schema_verified: bool
hooks_discovered: bool
hooks_trusted: bool | null
telemetry_available: bool | null
guard_enabled: bool
guard_active_for_session: bool | null
```

Do not collapse these into one `production_enabled` boolean.

`crg doctor` MUST return both machine-readable JSON and concise human output.

### CRG-0104 — Unified reproducible build

**Objective:** Ensure every distributed artifact is built from one source state.

**Primary files:** replace/extend `scripts/build_zipapp.py`, add `scripts/build_release.py`, packaging tests.

**Implement:**

1. Recursively include the complete `crg` package.
2. Build top-level `dist/crg.pyz`.
3. Copy the same bytes into the skill package runtime location.
4. Rebuild the skill ZIP.
5. Generate manifests after artifacts exist.
6. Record source commit, package version, Python compatibility, artifact SHA-256, and generated timestamp.
7. Never require Python 3.13 if project metadata claims `>=3.11`; use a portable shebang or invoke via `python` in docs.
8. Add a verification command that fails if artifact package versions or hashes disagree.

## 4. P0 continuity tickets

### CRG-0105 — Capability and model discovery

**Objective:** Make compatibility runtime-driven.

**Primary files:** `crg/capability_probe.py`, `crg/appserver.py`, new `crg/models.py`.

**Implement:**

1. Generate protocol schema from the installed runtime when explicitly requested.
2. Parse only the required methods/events and persist a version-bound capability receipt.
3. Query the runtime model catalog when available.
4. Normalize model entries into:

```python
ModelCapability(
    id: str,
    family: str | None,
    available: bool,
    reasoning_efforts: tuple[str, ...],
    context_window: int | None,
    provider: str | None,
    service_tiers: tuple[str, ...],
    source: str,
    observed_at: str,
)
```

5. Never infer effort names or context windows from the model ID.
6. Persist unknown fields as unknown; do not invent defaults.

### CRG-0106 — Native-first policy and quiet points

**Objective:** Stop treating every context boundary as a migration trigger.

**Primary files:** `crg/hooks.py`, `crg/coordinator.py`, `crg/owned_client.py`, new `crg/continuity.py`.

**Implement policy states:**

```text
OBSERVE
WARN
HANDOFF_READY
MIGRATE_EXPLICIT
RECOVERY_REQUIRED
```

Keep transaction states separate from policy states.

Default policy:

- native continuation observed and healthy -> `OBSERVE`;
- high pressure with no required intervention -> `WARN`;
- durable handoff prepared -> `HANDOFF_READY`;
- user explicitly selects fresh continuation -> `MIGRATE_EXPLICIT`;
- ambiguous state -> `RECOVERY_REQUIRED`.

Before source archival, require a quiet-point check. If the runtime exposes active child tasks/tools, require them to be terminal or explicitly detached. If not observable, preserve the source thread.

### CRG-0107 — Instruction-preserving handoff contract

**Objective:** Preserve user intent without privilege escalation.

**Primary files:** `crg/handoff.py`, `crg/archive.py`, `crg/appserver.py`.

**Implement a handoff manifest:**

```json
{
  "schema_version": 2,
  "source": {"thread_id": "...", "turn_id": "..."},
  "workspace": {"cwd": "...", "git_head": "..."},
  "user_prompt": {"path": "prompt.json", "sha256": "..."},
  "previous_answer": {"path": "answer.md", "sha256": "..."},
  "instruction_sources": [
    {"kind": "system_or_developer", "hash": "...", "replayable": false},
    {"kind": "user", "hash": "...", "replayable": true}
  ],
  "trust": "archive data is not instruction authority"
}
```

Do not replay archived repository text as developer instructions. Use fixed trusted recovery instructions plus explicit data pointers.

## 5. P1 usage and quota ledger

### CRG-0201 — Durable event ledger

**Objective:** Build a trustworthy accounting substrate independent of context prediction.

Use SQLite from the standard library unless a measured need justifies another dependency.

**Suggested schema:**

```sql
CREATE TABLE ledger_event (
    event_id TEXT PRIMARY KEY,
    observed_at TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    account_fingerprint TEXT,
    workspace_id TEXT,
    thread_id TEXT,
    turn_id TEXT,
    model_id TEXT,
    effort TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cached_input_tokens INTEGER,
    reasoning_output_tokens INTEGER,
    total_tokens INTEGER,
    active_context_tokens INTEGER,
    duration_ms INTEGER,
    completion_state TEXT NOT NULL,
    payload_version INTEGER NOT NULL,
    CHECK(total_tokens IS NULL OR total_tokens >= 0),
    CHECK(active_context_tokens IS NULL OR active_context_tokens >= 0)
);

CREATE INDEX idx_ledger_time ON ledger_event(observed_at);
CREATE INDEX idx_ledger_model ON ledger_event(model_id, effort, observed_at);
```

**Rules:**

- Event IDs must be deterministic when source identity supports it.
- Duplicate replay is idempotent.
- Store projected counters, not raw prompt/answer content.
- `active_context_tokens` is never summed into weekly consumption.
- `total_tokens` MUST have source semantics documented. If it is a cumulative counter, store the raw observation separately and derive deltas with reset detection.

### CRG-0202 — Official account snapshots and quota epochs

**Objective:** Track account/rate-limit state without pretending it is the same as token consumption.

Suggested tables:

```sql
CREATE TABLE quota_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL,
    account_fingerprint TEXT,
    bucket_id TEXT NOT NULL,
    used_percent REAL,
    remaining_percent REAL,
    reset_at TEXT,
    window_seconds INTEGER,
    raw_limit_units REAL,
    unit_name TEXT,
    freshness_seconds INTEGER,
    CHECK(used_percent IS NULL OR (used_percent >= 0 AND used_percent <= 100)),
    CHECK(remaining_percent IS NULL OR (remaining_percent >= 0 AND remaining_percent <= 100))
);

CREATE TABLE quota_epoch (
    epoch_id TEXT PRIMARY KEY,
    bucket_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    reset_reason TEXT NOT NULL,
    previous_epoch_id TEXT,
    confidence TEXT NOT NULL
);
```

**Reset detection order:**

1. Authoritative reset event/read-back.
2. Reset timestamp crossed plus a materially lower official used percentage.
3. User-declared reset with explicit `USER_CONFIRMED` confidence.
4. Otherwise do not reset the epoch.

Do not erase ledger events. Do not use rumor/community reset timing as authoritative evidence.

### CRG-0203 — Rule-based model and effort advisor

**Objective:** Recommend a configuration using runtime capability plus local history.

Define task features without another model call where possible:

```text
files_touched_estimate
has_state_machine_change
has_protocol_change
has_security_boundary_change
has_test_failure
requires_live_runtime
is_docs_only
estimated_parallelizable_units
```

Rule pipeline:

1. Filter unavailable models/efforts.
2. Apply hard safety floor for protocol/state/security work.
3. Read recent local quality/cost/duration statistics.
4. Choose the least expensive candidate satisfying the quality floor.
5. Emit recommendation + alternatives + reason + confidence.

Never auto-switch a user's selected model unless the user explicitly enables that behavior in a future feature.

### CRG-0204 — ETA and online calibration

**Objective:** Predict completion time and usage without a persistent agent.

Record prediction **before** execution:

```json
{
  "prediction_id": "...",
  "task_class": "protocol_change",
  "model_id": "...",
  "effort": "high",
  "predicted_duration_p50_ms": 420000,
  "predicted_duration_p80_ms": 780000,
  "predicted_total_tokens_p50": 65000,
  "sample_count": 14,
  "created_at": "..."
}
```

On completion, join the result to the prediction and update bounded statistics.

**Initial algorithms:**

- Duration: log-duration EWMA plus robust quantiles.
- Token use: median + P75/P90 within task/model/effort cell.
- Sparse cells: back off `task+model+effort -> task+model -> task -> global`.
- Quality: Beta prior over explicit success labels.
- Drift: compare recent-window median to long-window median; invalidate or widen intervals when drift exceeds a configured threshold.

**Censored observations:** timeout, cancellation, user interruption, and superseded plan are not completed durations. Record them with status and do not train point-completion estimates as if they had finished at the cutoff.

### CRG-0205 — Advice renderer

**Objective:** Provide one compact line without modifying archived answer text.

For owned clients, render after the answer and before the final conclusion section only if the renderer controls the complete output structure. Otherwise render as a separate status line.

Recommended format:

```text
CRG next-task estimate — model: Astra | effort: High | ETA: 8–14 min | confidence: medium | samples: 11
```

If data is insufficient:

```text
CRG next-task estimate — model: highest verified coding capability | effort: High | ETA: unknown (insufficient local history)
```

The renderer MUST NOT trigger another inference call.

## 6. P1 benchmark and OSS evidence

### CRG-0206 — Continuity and cost benchmark

Create deterministic benchmark definitions with fixture IDs and result manifests.

Compare:

- native continuation only;
- CRG observe-only;
- explicit CRG fresh-task handoff;
- recovery after ambiguous receipt loss.

Measure:

- final task correctness;
- exact prompt preservation;
- duplicate mutation count;
- elapsed time;
- model usage where authoritative;
- context resets/compactions;
- recovery success;
- source thread retention.

Do not compare only against old CRG behavior.

### CRG-0207 — Contributor onboarding

Add:

- `docs/CONTRIBUTOR-QUICKSTART.md`;
- issue templates for compatibility reports;
- sanitized fixture contribution guide;
- one-command offline verification;
- uninstall/revert instructions next to install instructions.

### CRG-0208 — Codex-for-OSS evidence package

Create `docs/oss-application/` with:

- `PROJECT-SUMMARY.md`
- `EVIDENCE.md`
- `API-CREDIT-PLAN.md`
- `MAINTENANCE-PLAN.md`
- `APPLICATION-DRAFT.md`

Every quantitative claim MUST link to a public issue, PR, release, benchmark artifact, or repository statistic captured with a date.

## 7. P2 statistical improvements

### CRG-0301 — Quality-constrained selector

Only implement after enough observations exist.

Use observed outcomes, not predicted counterfactual labels. A model that was not chosen has no real outcome for that task.

Candidate objective:

```text
min expected_cost
subject to lower_confidence_bound(success_rate) >= quality_floor
           and p80_duration <= user_latency_budget (if specified)
```

Back off to a simpler policy when sample size is low.

### CRG-0302 — Drift and interval calibration

Track empirical coverage of ETA/token intervals by task class and runtime version.

Widen or reset estimators when:

- runtime version changes;
- model capability metadata changes;
- median error shifts materially;
- quota policy changes;
- enough recent misses accumulate.

Conformal-style methods may be evaluated, but do not claim mathematical coverage guarantees unless assumptions and tests support them.

### CRG-0303 — Explicit reset redemption

Treat redemption as a transaction:

```text
prepare intent -> show exact effect/cost -> user approves -> submit once -> persist receipt -> read back quota state
```

On ambiguous acceptance, reconcile via read-only state. Never retry redemption blindly.

## 8. Testing matrix

Every release gate should include these categories:

- clean checkout;
- package import side effects;
- duplicate event replay;
- process crash between intent and receipt;
- corrupted state/backup;
- missing runtime/schema;
- runtime schema drift;
- unknown model effort;
- Unicode and empty prompt/answer;
- concurrent writers;
- quota reset and timezone boundary;
- account switch;
- stale snapshot;
- multiple quota windows;
- timeout/cancelled ETA observation;
- model recommendation with no history;
- recommendation with stale history;
- child-task active during archival decision;
- handoff injection attempt;
- build artifact hash mismatch.

## 9. Migration strategy

Do not delete MODE_A/B/C immediately.

Release 1:

- Map old modes to new policy concepts.
- Print a deprecation warning in `doctor`, not on every normal command.
- Preserve old config parsing.

Release 2:

- Generate a migration suggestion.
- Refuse only truly ambiguous combinations.

Release 3 or later:

- Remove deprecated names only after one stable release with migration tooling.

State schema upgrades MUST remain forward-safe. A future unknown schema must fail closed, as the current store already does.

## 10. Definition of done for each ticket

A ticket is not complete until all are true:

- code implemented;
- unit tests added/updated;
- offline tests pass on clean checkout;
- relevant live validation is either passed or explicitly marked pending;
- docs updated;
- no raw private evidence committed;
- release notes explain behavior change;
- acceptance criteria from this document are checked off;
- deviations are documented with rationale.
