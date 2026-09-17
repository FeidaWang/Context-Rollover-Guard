# Context Rollover Guard — Actionable Product and OSS Roadmap

Review baseline: `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`

## 1. Product direction

Preserve CRG's strongest asset: fail-closed continuity and recovery. Reposition the project from “prevent compaction and force a new task” to:

> **Local-first continuity, trustworthy usage accounting, and low-overhead next-task advice for Codex.**

Implement a **native-first** policy. Native continuation mechanisms remain the default path when they are available and healthy. CRG should intervene only when the user explicitly requests a fresh task, when a verified compatibility condition requires migration, or when recovery is necessary.

Do not make “context compaction happened” equivalent to “CRG failed.” The product should measure whether work remains correct, recoverable, and efficient across context boundaries.

## 2. Primary success objective

Optimize implementation order for these outcomes, in this order:

1. A clean checkout can be tested by an external maintainer without private machine evidence.
2. Installation and failure modes are understandable and reversible.
3. CRG coexists with native continuation instead of competing with it by default.
4. Usage and quota data is auditable and correctly scoped.
5. Recommendation and ETA logic improves through local history without a background agent.
6. The repository has enough public evidence to support a credible Codex-for-OSS application.

Stars, forks, and downloads are supporting evidence only. Do not manufacture activity or optimize the project around vanity metrics.

## 3. Release gates

### M0 — Reproducible foundation (`v0.1.1` target)

Implement `CRG-0101` through `CRG-0104`.

Required deliverables:

- Safe repository defaults.
- Public protocol fixtures that replace author-machine evidence in unit tests.
- CI that runs on a clean checkout.
- Explicit runtime paths and a `doctor` output that separates configured, available, verified, and active states.
- One build command that produces every distributable artifact from the same source tree.

Exit criteria:

- `python -m unittest discover -s tests/unit -v` runs without requiring ignored private evidence.
- Offline self-test runs without Codex authentication or live model usage.
- Importing the package creates no hooks, threads, archives, or background services.
- Missing live evidence causes an explicit `UNKNOWN` or `UNVERIFIED` result, not a false success.
- All generated artifacts contain the same package version and manifest hash set.

### M1 — Native-first continuity (`v0.2.0` target)

Implement `CRG-0105` through `CRG-0107`.

Required deliverables:

- Runtime capability discovery from generated schema plus `model/list` or the current equivalent.
- Separation of transport ownership from guard policy.
- Native-first continuation policy.
- Quiet-point checks before source-thread archival.
- Instruction-preserving handoff manifests.

Exit criteria:

- CRG does not automatically replace a native continuation path that has not failed.
- Active tools or child tasks prevent automatic archival when completion cannot be proven.
- Handoff data never becomes higher-authority developer instructions merely because it was archived.
- Unknown model capabilities degrade to observation-only behavior.

### M2 — Usage ledger and decision assistance (`v0.3.0` target)

Implement `CRG-0201` through `CRG-0205`.

Required deliverables:

- Durable local event ledger.
- Optional official account-usage/rate-limit snapshots when the runtime exposes them.
- Quota epochs that survive reset events without deleting historical consumption.
- Rule-based model/effort recommendation with zero default additional inference calls.
- ETA intervals with sample counts and stale-data detection.
- A compact recommendation footer/status surface.

Exit criteria:

- Local usage, account usage, active context, and rate-limit windows are never merged into one number.
- Reset events start a new quota epoch while preserving historical usage.
- Remaining percentage is not converted into a fixed token balance unless an authoritative token denominator exists.
- ETA uses completed observations only; timeouts/cancellations are marked as censored or incomplete.
- Recommendation failure never blocks task execution.

### M3 — Public evidence and OSS application

Implement `CRG-0206` through `CRG-0208` in parallel with M2.

Required deliverables:

- Continuity benchmark comparing native-first, guarded handoff, and recovery paths.
- Public compatibility matrix.
- At least one externally reproducible user or maintainer report.
- A bounded API-credit budget plan tied to open-source maintenance outcomes.
- Codex-for-OSS application text backed by repository evidence.

Exit criteria:

- Benchmark failures are published, not filtered out.
- Every adoption claim links to public evidence or is explicitly labeled anecdotal.
- Application text does not claim guaranteed eligibility or invent usage metrics.

### M4 — Statistical calibration and optional automation (`v0.4.0+`)

Implement `CRG-0301` through `CRG-0304` only after M2/M3 produce sufficient data.

Required deliverables:

- Shrinkage or hierarchical estimates across sparse task/model cells.
- Drift detection and interval recalibration.
- Optional reset redemption with explicit user authorization and read-back verification.
- Attachment/Windows support only when backed by real demand and tests.

Exit criteria:

- Advanced methods beat simple baselines on a time-split evaluation without reducing safety.
- No automatic spending action occurs without explicit authorization.
- Any model-family adapter is discovered from runtime evidence, not from a guessed future model ID.

## 4. Priority backlog

| ID | Priority | Deliverable | Depends on | Acceptance focus |
|---|---|---|---|---|
| CRG-0101 | P0 | Safe defaults and truthful platform behavior | — | No implicit production action from clone/import/self-test |
| CRG-0102 | P0 | Public fixtures and clean CI | 0101 | Unit tests do not require private evidence |
| CRG-0103 | P0 | RuntimePaths, init, doctor | 0101 | Configured/available/verified/active are distinct |
| CRG-0104 | P0 | Unified reproducible build | 0102 | Source, pyz, skill ZIP, manifests agree |
| CRG-0105 | P0 | Capability/model discovery | 0102,0103 | Dynamic schema and effort support; unknown degrades safely |
| CRG-0106 | P0 | Native-first continuity and quiet points | 0105 | No premature migration or archival |
| CRG-0107 | P0 | Instruction-preserving handoff contract | 0106 | No privilege escalation from archived content |
| CRG-0201 | P1 | Durable usage/event ledger | 0103,0105 | Deduplication, provenance, scope separation |
| CRG-0202 | P1 | Account snapshots and quota epochs | 0201 | Reset without history loss; no fake token denominator |
| CRG-0203 | P1 | Rule-based model/effort advisor | 0105,0201 | Capability filtering and explainable choices |
| CRG-0204 | P1 | ETA prediction and online updates | 0201,0203 | Pre-result prediction, censored outcomes, uncertainty |
| CRG-0205 | P1 | Compact advice/status renderer | 0103,0203,0204 | Separate renderer from preserved answer text |
| CRG-0206 | P1 | Continuity/cost benchmark | 0106,0201 | Compare against native baseline |
| CRG-0207 | P1 | Contributor onboarding and demos | 0104,0205 | External maintainer can install/test/recover |
| CRG-0208 | P1 | Codex-for-OSS evidence package | 0206,0207 | Claims are sourced and bounded |
| CRG-0301 | P2 | Quality-constrained selector | 0203,0206 | No false counterfactual claims |
| CRG-0302 | P2 | Drift and interval calibration | 0204,0206 | Coverage tracked by group and time |
| CRG-0303 | P2 | Explicit reset redemption | 0202 | User authorization, idempotent intent, read-back |
| CRG-0304 | P2 | Attachments/Windows adapters | External demand | Preserve exactness and safety invariants |
| CRG-0401 | P3 | Future model-family adapter | Official/runtime availability | No guessed IDs or static capabilities |

## 5. User-facing product rules

Implement these rules before adding richer UI:

- Default install mode is observe-only.
- Guarding must be explicit and reversible.
- Display source and freshness for every usage/quota number.
- Display `unknown` when coverage is incomplete.
- Never show a precise “tokens remaining” number from a percentage-only rate limit.
- Never hide that multiple devices or cloud tasks may be outside local coverage.
- Preserve the original answer separately from recommendation UI.
- Give the user the final decision on model and reasoning effort.

## 6. Model and effort policy

Do not maintain a hardcoded “Astra > Sol > Luna” decision table in production code. Implement a two-stage selector:

1. **Capability filter** — only consider models and efforts reported as available by the current runtime/account/workspace.
2. **Local policy** — choose the lowest-cost configuration that satisfies task-risk requirements and historical quality constraints.

Cold-start policy:

- Safety-critical state/recovery/compatibility changes: highest-capability coding model available; prefer Astra + High when available.
- Medium implementation work with bounded files and tests: capable general coding model + Medium/High.
- Mechanical docs, formatting, or deterministic test updates: lower-cost model when capability is sufficient.
- Ultra/Extra-High: opt in only when the task contains deep multi-file reasoning, repeated failed debugging, or independent parallel subproblems.

If a future `GPT-6 Sol` appears, add it only after runtime discovery and compatibility tests. Never pre-create a production identifier based on naming expectations.

## 7. Low-overhead continuous learning target

Implement local learning as an event-driven update, not a background agent:

```text
before task -> save prediction and selected configuration
on completion -> save observed duration/usage/outcome
score prior prediction -> update bounded local statistics
on next task -> compute recommendation from stored statistics
```

No background model call is required. Use constant-time or bounded-window updates. Store enough data to audit the recommendation.

Initial statistics:

- Exponentially weighted mean for stable central tendency.
- Robust median/MAD or quantile sketch for heavy-tailed duration and token usage.
- Beta-Binomial style success-rate smoothing for sparse quality outcomes.
- Recency decay or rolling windows for model/runtime drift.
- Prediction intervals rather than point guarantees.

Do not call this an RSI. If an RSI-like display is desired, expose a bounded **efficiency pressure index** derived from normalized recent usage, duration, and remaining quota, while keeping the underlying components visible. The index must not replace raw metrics.

## 8. Codex-for-OSS preparation

Build an evidence folder that contains:

- Repository purpose and architecture summary.
- Reproducible test commands.
- Compatibility matrix.
- External maintainer report(s).
- Benchmark results with methodology.
- Security and privacy boundaries.
- Exact API-credit usage plan.
- Links to releases/issues/PRs demonstrating ongoing maintenance.

Suggested API-credit allocation for the application narrative:

- 40% representative maintenance-task comparisons.
- 30% recovery and cross-model compatibility validation.
- 20% real project maintenance, PR review, and release validation.
- 10% reruns and version-change reserve.

Calculate requested credits only after a pilot:

```text
requested_budget = preregistered_tasks
                 * configurations_per_task
                 * repetitions
                 * median_observed_cost
                 * reserve_factor
```

Do not estimate the budget from one flat token price when input, output, cached, service-tier, or model pricing differ.

## 9. Community growth plan

Prioritize useful contributor entry points:

- Add or sanitize a protocol fixture.
- Add a timezone/reset regression test.
- Validate one installation path.
- Improve one failure message.
- Reproduce one runtime compatibility case.

Create demonstrations for:

1. Recovery after acceptance-receipt loss without replay.
2. Native continuation working while CRG stays out of the way.
3. Quota reset creating a new epoch without erasing historical consumption.

Measure:

- clean-install success rate;
- time to first useful result;
- number of externally verified environments;
- recovery correctness;
- duplicate-submission incidents;
- prediction interval coverage;
- fraction of observations marked unknown/incomplete.

Do not optimize only for stars.

## 10. First Codex execution prompt

Use this prompt for the first implementation batch:

```text
Work in FeidaWang/Context-Rollover-Guard.
Read docs/implementation/00-START-HERE.md, 01-ROADMAP.md, and 02-TECHNICAL-IMPLEMENTATION.md.
Implement only CRG-0101 and CRG-0102.

Constraints:
- Preserve fail-closed mutation handling.
- Do not add background services or automatic model calls.
- Do not depend on ignored machine-specific evidence for unit tests.
- Keep the public default observe-only and platform-neutral.
- Add tests before changing behavior when practical.
- Run the full clean-checkout unit suite and offline self-test.
- Report changed files, test results, unresolved runtime-only validation, and any specification deviation.
- Do not begin CRG-0103 or later tickets unless required to make 0101/0102 testable.
```
