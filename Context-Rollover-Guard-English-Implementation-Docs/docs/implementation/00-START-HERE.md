# Context Rollover Guard — Implementation Entry Point

Baseline reviewed: `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`

Use this document set as an execution package for Codex. Treat every task as an implementation contract, not as a product claim. Do not claim a feature is supported until the corresponding acceptance gate passes on a clean checkout.

## Read in this order

1. `01-ROADMAP.md` — product direction, release gates, OSS growth strategy, and Codex-for-OSS evidence plan.
2. `02-TECHNICAL-IMPLEMENTATION.md` — implementation tickets with files, changes, invariants, tests, and acceptance criteria.
3. `03-AUDIT-AND-SOURCES.md` — repository audit scope, evidence levels, assumptions, and source references.

## Mandatory execution rules

- Re-read `main` before starting a ticket. If the target code changed, update the ticket implementation notes before editing code.
- Change one contract per pull request whenever practical. Do not combine state-machine changes, packaging changes, accounting semantics, and model-selection changes in one PR.
- Preserve the existing fail-closed behavior: ambiguous mutation acceptance MUST NOT cause an automatic retry.
- Do not hardcode model capabilities from model names. Discover capabilities from the installed runtime and generated schema.
- Keep raw prompts, answers, credentials, and account identifiers out of public fixtures and telemetry exports.
- Every new metric MUST define scope, source, time basis, reset semantics, and unknown-state behavior.
- Every user-visible estimate MUST expose uncertainty and sample count. Unknown data MUST stay unknown; never silently replace it with zero.
- New recommendation logic MUST default to zero additional model calls. Local computation, file I/O, and account reads are still real costs and must not be described as “zero cost.”

## First execution batch

Implement only these first:

- `CRG-0101` Safe defaults and platform-neutral configuration.
- `CRG-0102` Clean-checkout fixtures and CI.

Do not start quota redemption, advanced statistical learning, or automatic model switching before these two gates pass.

## Suggested execution model

Use the highest-capability coding model available in the current runtime for the P0 compatibility and state-safety work. Prefer Astra with High reasoning when available. Do not select Ultra/Extra-High by default unless the task contains independent parallel work or repeated deep debugging that justifies the higher cost.
