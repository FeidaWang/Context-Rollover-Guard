# M4 offline evaluation and adapter contracts

Status: **experimental/offline only**, 2026-09-17. The request to begin CRG-0301–0401 authorizes this preparatory implementation; it does not supply the real M2/M3 evidence required to activate advanced policies. Existing `advise`, `predict`, chat routing and runtime defaults are unchanged.

## Quality/cost and calibration audit (CRG-0301/0302)

```sh
python3.13 -m crg statistical-audit --input observations.jsonl \
  --split-at 2026-09-01T00:00:00Z --quality-floor 0.9 \
  --minimum-samples 30 --latency-budget-ms 600000
```

Use a supported Python 3.11+ executable. The command reads explicitly provided projected JSONL and prints a report; it does not modify a model, estimator, ledger or account. Each record has these fields:

| Fields | Contract |
|---|---|
| `task_id` | Unique chosen task attempt; identical replays deduplicate, conflicting outcomes/models fail |
| `task_class`, `runtime_version`, `capability_revision`, `quota_epoch` | Nonempty explicit grouping identities; changing any starts a separate group |
| `model_id`, `effort` | Actual selected action; no label for an unchosen action |
| `currency`, `source`, `evidence_kind` | Explicit comparable cost units/source; evidence kind `real` or `synthetic`; groups never mix units or kinds |
| `chosen` | Must be `true` |
| `predicted_at`, `observed_at` | Timezone-aware timestamps, strictly prediction before outcome |
| `status` | `completed`, `failed`, `timeout`, `cancelled` |
| `success` | Explicit boolean or null; censored outcomes must be null; failed cannot be true |
| `cost`, `duration_ms`, `total_tokens` | Finite nonnegative measured values or null; no price/usage inference |
| `duration_interval_ms`, `token_interval` | Pre-task `[lower, upper]` values or null; never fit these after observing the result |

Other fields (including raw prompts) are rejected. Claimed timestamps and provenance are supplied evidence, not independently authenticated. The existing estimate ledger has no measured monetary cost or token interval: do not invent either to produce this input. Real collectors must join immutable pre-task records, factual quality labels and authoritative costs.

Training outcomes precede the cutoff; test predictions start at or after it. Tasks crossing the cutoff are counted but excluded. For each action, the experimental selector requires the configured minimum (default 30), complete labels/costs, a descriptive 95% Wilson lower success bound above the floor, and a nearest-rank p80 duration within the optional budget. A 30/30 success record does **not** clear the default 0.9 floor. Candidates are ranked by mean observed cost. Sparse/incomplete cells return `EXISTING_EXPLICIT_POLICY`; no fallback action is automatically executed. Historical actions are not proof of current availability or safety approval; any later activation must additionally apply the existing capability/safety filter.

The held-out report counts only factual matches. It leaves counterfactual quality and selector baseline improvement null; biased observational data cannot establish performance of actions that were not run. `production_ready` is always false.

Coverage is reported separately by action and UTC day within each context group, for completed predictions with observed measurements. Drift uses the latest 200 scored observations across days: fewer than 8 hits in the last 10, or a median residual shift relative to earlier errors. These are initial policy constants, not calibrated guarantees. It reports a reset recommendation, never mutates the live estimator.

A separate candidate interval widening uses the training-set p80 nonnegative interval residual after the minimum sample count. Original and widened intervals are evaluated on the *same* held-out rows. Wider intervals can improve coverage at the cost of precision; no improvement claim follows merely from more hits. Context-group changes cannot borrow an old correction. No conformal or distribution-free guarantee is asserted. Sparse-cell hierarchical shrinkage and production estimator activation remain deferred until real baseline evidence is available.

## Explicit reset engine (CRG-0303)

`crg.redemption.Redemptions` is a durable engine, with **no production adapter and no submission CLI**. It is exercised only against injected synthetic adapters in this batch.

1. `prepare` stores an immutable account/contract/effect/cost intent, UUID idempotency key, digest and at-most-five-minute expiry.
2. The host displays the exact effect and cost and obtains fresh human approval of that digest. A Python boolean is not a user-interface approval mechanism; implementing that UI is a prerequisite for a production host.
3. `submit` checks approval/expiry and fresh same-account eligibility. SQLite claims `SUBMITTING` before calling the adapter. Other ambiguous/accepted intents for that account block a new submission.
4. The adapter must atomically enforce `expected_account`, `expected_contract`, `approved_effect`, `approved_cost` and the idempotency key at the actual mutation boundary. A preceding read alone is insufficient.
5. A projected receipt is persisted before readback. An accepted receipt with failed readback remains `ACCEPTED`; it is never resubmitted.
6. `reconcile` uses only authoritative lookup by intent ID and keyed same-account readback. A quota drop alone cannot prove redemption. Missing receipt remains ambiguous indefinitely; there is no automatic retry or timeout clearing.

Adapter contract: stable `contract_id`; read-only `read_state()` with account/contract/eligibility and authoritative `redeemed_intent_id`; `submit(...)` returning matching intent/account and `accepted`, `no_credit` or `ineligible`; read-only `lookup(intent_id)` returning that receipt or null. No existing live service is claimed to implement this interface. Contract verification, atomic account binding, host approval UI, error mapping and exact current credit effects must be independently established first. Raw account responses and credentials are not persisted.

## Attachments / Windows (CRG-0304)

**Deferred, not implemented or accepted.** The archive and owned-client inputs currently support exact text; the persistence layer uses POSIX `fcntl`, `O_NOFOLLOW` and directory fsync. An untested platform shim would weaken existing invariants.

Required before delivery:

- A defined attachment transport, explicit file selection and supported media/size scope.
- Byte/hash roundtrip fixtures for binary, empty, Unicode-named and multiple attachments; reject missing, changed, oversized and traversal/symlink inputs without silent text conversion.
- Crash/replay tests proving one forwarded request with unchanged attachment bytes and no privilege elevation through metadata.
- A Windows implementation and real Windows CI for file ACLs, reparse points, atomic persistence, locking, fsync equivalents, interruption and recovery.

The current macOS offline suite is not Windows or attachment evidence. This task is not silently marked complete.

## Runtime-discovered model adapter (CRG-0401)

```sh
python3.13 -m crg resolve-model --catalog catalog.json \
  --model EXACT_RUNTIME_ID --effort EXACT_RUNTIME_EFFORT \
  --at 2026-09-17T00:00:00Z
```

The input can be the existing doctor/probe JSON or a projected catalog. Resolution requires one available exact ID, an explicitly exposed effort and a catalog no more than one hour old. It returns a metadata revision and preserves unknown family/context/provider fields. `--expected-revision` rejects metadata changes and requests estimator reset. Unknown/stale/changed requests return exit 2. This command consumes supplied catalog evidence; it does not authenticate a hand-written `VERIFIED_CATALOG` flag, perform live discovery or switch a model. Production callers must obtain it through the existing verified probe path. An unfamiliar synthetic ID proves generic handling, not availability of any future model family.
