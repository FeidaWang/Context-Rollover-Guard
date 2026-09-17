# Safe defaults and native-cooperative continuity

CRG starts disabled. Import, configuration inspection and offline self-tests do not
register hooks or edit Codex configuration. Explicit hook installation remains a
separate operation. Enabling CRG does not discover all sessions: the repository
adapter reads only the hook-bound workspace/session and explicitly supplied source.

## Independent dimensions

`context_rollover.mode` is the existing MODE_A/B/C control-capability dimension.
`continuity.policy` expresses desired behavior and never establishes capability,
trust, an owned transport, or permission to change execution settings.

| Policy | Enabled hook behavior | Authority |
|---|---|---|
| `observe` | No hook writes or interception | Read/explain through explicit observation commands |
| `native_cooperative` (default) | Save exact Stop answer and available auto-compaction snapshot; allow native continuation | Explicitly enabled, bound source only |
| `manual_recovery` | Same non-intercepting snapshots; user chooses a handoff | No automatic thread creation or forwarding |
| `guarded_owned_rollover` | Guard handlers may act only with verified adapter flags, MODE_B and explicit emergency settings | Policy alone grants nothing; owned fresh recovery separately requires explicit user request and existing transaction checks |

The CLI and repository hook adapters have no verified current-session interception
contract. They therefore supply no warning/arming or blocking capability flags.
Legacy CLI `--allow-*` flags remain parseable but do not grant such capabilities.
They do not cause a nonzero exit solely because they were supplied. Embedded
`HookDispatcher` adapter flags are a trusted integration boundary, not a runtime
probe; synthetic unit tests exercise both authorized and unauthorized paths. No
public hook adapter is currently certified for interception. Do not interpret
MODE_B in a configuration file or a cached version string as verification.

Cooperative/manual policies suppress legacy emergency blocking/force settings even
if an embedded adapter supplies flags. They do not clear existing ARMED, pending,
ambiguous or RECOVERY_REQUIRED records. Recovery inspection and positive-only
reconciliation remain available; switching policy cannot replay or erase an input.
Explicit `chat` fresh requests retain their existing owned-transport authorization
and recovery checks; this task does not redesign that transaction engine.

## Native feature evidence

| Evidence | Meaning | Behavior |
|---|---|---|
| Unknown | No bound observation, incomplete metadata or unsupported contract | Do not claim native activation; retain conservative recovery and non-blocking behavior |
| Unavailable or explicitly disabled | An actual capability/config result says the feature is absent/off | Explain absence; offer manual recovery, never infer permission to intercept or install |
| Verified for current runtime/session | A specific adapter has positive version/session-bound evidence | Cooperate with that observed feature; no automatic increase in CRG authority |

A cached schema hash, model name, synthetic fixture or native token counter is not
proof that native memory/compaction is enabled. No new Codex feature names or
activation keys are guessed here. Snapshot I/O failures and installed hook failure
policy need the separate CRG-1007 review; offline PASS does not certify host behavior.

## Configuration compatibility and migration

Precedence stays defaults < user CRG file < repository CRG file < explicit overrides.
`config` and `doctor` expose diagnostics when continuity policy is implicit or old
emergency flags are inactive. `predictor.warn_probability` remains accepted and
range-validated, but is deprecated and ignored. It was not used as a threshold.
The predictor's `risk_score` is an uncalibrated growth-plus-buffer/headroom ratio;
`calibrated_probability` stays false. No numerical decision rule changed.

Preview the workspace file without writes:

```sh
python3.13 -m crg config migrate --workspace /path/to/project --dry-run
```

After reviewing its `candidate` and `source_sha256`, explicitly create a separate
candidate file:

```sh
python3.13 -m crg config migrate --workspace /path/to/project --apply \
  --output crg.candidate.toml --expected-sha256 <source_sha256-from-preview>
```

This appends a missing continuity table, preserving original bytes/comments and
explicit settings. It does not activate the candidate, overwrite `crg.toml`, copy
user-level settings, change permissions, install hooks or touch recovery records.
The destination must be a new direct-child TOML file. Stale source hashes, symlink
sources/destinations, existing outputs and outside-workspace targets are refused.
An existing continuity table without a policy requires an explicit manual edit;
the migrator does not guess TOML table boundaries. Inspect the candidate before
separately choosing whether to adopt it. Old guard values remain present but do
not authorize interception under the cooperative default.

## Verification scope

Run `python3.13 docs/audit/verify_safe_defaults.py` for a disposable source snapshot,
empty HOME/CODEX_HOME, an allowlisted environment and no Codex on PATH. Tests cover
configuration precedence, import side effects, shipped self-test isolation, native
continuation, exact text, permission refusal, adapter capability boundaries and
migration non-overwrite/stale-source behavior. The shipped self-test exercises the
existing distribution; this task does not rebuild release artifacts. OS network
isolation, hosted CI and live native contracts remain unverified.
