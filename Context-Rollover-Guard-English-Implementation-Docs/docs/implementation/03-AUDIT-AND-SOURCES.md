# Context Rollover Guard — Audit Scope and Evidence Guide

Review date: 2026-09-17

Repository baseline:

```text
repository: FeidaWang/Context-Rollover-Guard
main:       8079b5c3e87b0e74d79f56c3c3236060fc62cdc6
initial:    9475d17cf10a9950932b10c4f5de65c2d6bfe61b
```

Use this file to keep implementation claims honest. When a later commit changes relevant code, update the audit baseline before using an old conclusion as current fact.

## 1. Evidence labels

Use these labels in issues, PRs, release notes, and application materials:

- `STATIC_REVIEW` — conclusion from source/config inspection only.
- `OFFLINE_TEST` — reproduced without live Codex model/account access.
- `LIVE_ISOLATED_TEST` — reproduced against a controlled live runtime/thread that does not take over the user's active Desktop task.
- `PRODUCTION_OBSERVATION` — observed in a real user workflow with consent and documented scope.
- `OFFICIAL_DOCUMENTATION` — documented by the platform/provider, but not necessarily observed on the user's runtime.
- `DESIGN_PROPOSAL` — planned behavior, not implemented evidence.
- `UNKNOWN` — insufficient evidence.

Never rewrite `STATIC_REVIEW` as “tested” or `OFFICIAL_DOCUMENTATION` as “verified on this machine.”

## 2. Repository findings that drive the roadmap

### A. Strong safety foundation

Relevant files:

- `crg/coordinator.py`
- `crg/recovery.py`
- `crg/owned_recovery.py`
- `crg/archive.py`
- `crg/state_store.py`

Observed design properties (`STATIC_REVIEW`):

- Mutation intent is persisted before dangerous operations.
- Ambiguous acceptance enters recovery instead of blind retry.
- Positive read-back is used to reconcile forwarding/archive state.
- Prompt and answer archives include integrity checks.
- State is protected by checksums, locking, backups, and fail-closed schema handling.

Implementation instruction: preserve these properties when adding account actions, reset redemption, or model switching.

### B. Active-context and cumulative usage are already separated

Relevant files:

- `crg/telemetry.py`
- `crg/repo_hook.py`
- `crg/predictor.py`

Observed design property (`STATIC_REVIEW`): `tokenUsage.last.totalTokens` is treated as active context while cumulative totals are stored separately. Missing active telemetry is not replaced by cumulative totals.

Implementation instruction: keep this distinction in the new ledger. Weekly consumption must not sum active-context samples.

### C. Current predictor is heuristic, not calibrated probability

Relevant file: `crg/predictor.py`.

Observed design (`STATIC_REVIEW`): prediction uses recent positive deltas, P75/latest/median scaling, and a safety buffer. `risk_score` is a ratio-like heuristic and `calibrated_probability` is false.

Implementation instruction: keep the user-visible label as heuristic until empirical calibration is implemented and measured.

### D. Repository configuration is not a safe public default

Relevant files:

- `crg.toml`
- `crg/config.py`

Observed (`STATIC_REVIEW`): repository config enables MODE_B, contains a machine-specific Codex binary path, and enables blocking behavior.

Implementation instruction: fix this before promoting the repository as easy to clone and try.

### E. Offline tests reference machine-specific evidence paths

Relevant tests include schema/evidence paths under `docs/context-rollover/evidence` while that tree is intentionally ignored from version control.

Evidence level: `STATIC_REVIEW`; this audit did not execute the clean-checkout suite.

Implementation instruction: add committed sanitized fixtures and make live evidence optional.

### F. Build flow can drift

Relevant files:

- `scripts/build_zipapp.py`
- `dist/MANIFEST.json`
- `dist/context-rollover-guard.manifest.json`
- `dist/crg.pyz`
- `dist/context-rollover-guard/scripts/crg.pyz`

Observed (`STATIC_REVIEW`): the build script copies top-level package files and updates one primary artifact path; the process does not provide one explicit atomic release build that regenerates every distribution artifact and manifest.

Do NOT claim the currently committed pyz files are different unless a byte/hash comparison proves it. The finding is about reproducibility risk.

## 3. Files covered by the audit

The review covered the tracked human-readable source/config/test files visible in the baseline tree, including:

- root manifests, README, CONTRIBUTING, SECURITY, config and packaging files;
- all `crg/*.py` runtime modules;
- skill Markdown/YAML/reference files under `dist/context-rollover-guard`;
- unit, integration, live-test, and support Python files under `tests/`;
- release manifest text files.

Binary `.pyz` and `.zip` artifacts were identified through repository metadata but were not independently unpacked/executed in the original review. Treat any behavior claim about their internal bytes as `UNKNOWN` until verified.

## 4. Validation that was NOT completed in the original review

Do not claim these were completed unless a later PR adds evidence:

- Full unit suite on a clean clone.
- Live Codex runtime validation for the maintainer account.
- Real account usage/rate-limit reads.
- Real reset redemption.
- Production Desktop UI switching.
- Independent execution of committed `.pyz`/`.zip` artifacts.
- Cross-platform Windows behavior.
- Any official `GPT-6 Sol` production ID or capability set not exposed by the runtime.

## 5. External source policy

The roadmap was informed by these source categories. Re-check dynamic documentation before implementation that depends on current protocol/model behavior.

### Codex for OSS

- Application form: `https://openai.com/zh-Hans-CN/form/codex-for-oss/`
- Terms: `https://learn.chatgpt.com/docs/codex-for-oss-terms`

Use for application fields, eligibility framing, and support terms. Do not infer guaranteed credits or approval probability.

### Codex App Server / runtime protocol

- `https://learn.chatgpt.com/docs/app-server`

Use as supplemental documentation. The installed generated schema and runtime responses remain the compatibility authority for CRG adapters.

### Hooks

- `https://learn.chatgpt.com/docs/hooks`

Use for hook concepts and supported surfaces. Do not treat `systemMessage` as an API for rewriting an already produced answer.

### Model documentation

- GPT-5.6: `https://openai.com/index/gpt-5-6/`
- GPT-6 Astra: `https://openai.com/index/gpt-6-astra/`
- Latest-model/developer guidance: `https://developers.openai.com/api/docs/guides/latest-model`

Use runtime discovery for actual production IDs and effort support. Do not create future IDs from naming patterns.

### Codex plan usage/reset behavior

- `https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan`

Use to understand that rate limits and resets may represent shared agentic usage and may change over time. Always prefer actual account snapshots for current user state.

### Statistical reference

Adaptive Conformal Inference under distribution shift:

- `https://arxiv.org/abs/2106.00170`

Use only as research input for later calibration experiments. Do not claim formal coverage guarantees for CRG without validating assumptions and empirical coverage.

## 6. Claim checklist for future PRs

Before writing “supports,” “verified,” “accurate,” “exact,” or “zero-cost,” answer all of these:

1. What is the evidence label?
2. Which runtime/model/version was used?
3. What account/workspace/surface scope applies?
4. Was the result measured on a clean checkout?
5. Is the behavior implemented in source only, or also in release artifacts?
6. Can an external maintainer reproduce it?
7. Are missing values shown as unknown?
8. Are raw prompts/answers excluded from published evidence?
9. If a percentage is shown, is the denominator authoritative?
10. If a recommendation is shown, is the user still in control?

If any answer is unclear, downgrade the claim and document the missing evidence.

## 7. Update procedure

Whenever `main` changes a file involved in this roadmap:

1. Record the new commit SHA.
2. Compare the old and new commit for affected files.
3. Mark invalidated audit conclusions as stale.
4. Re-run clean-checkout tests.
5. Re-run only the live tests needed for changed runtime contracts.
6. Update compatibility matrix and release notes.
7. Keep old evidence immutable and timestamped; do not overwrite history to make a new version look consistent.
