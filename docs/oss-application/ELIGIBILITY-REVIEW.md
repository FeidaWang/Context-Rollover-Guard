# Codex for OSS readiness review

Observed 2026-09-18. Sources: the [official form](https://openai.com/zh-Hans-CN/form/codex-for-oss/), [program page](https://developers.openai.com/community/codex-for-oss), and [public repository](https://github.com/FeidaWang/Context-Rollover-Guard). Repository observations were checked through the existing browser tab and GitHub API. This is an evidence assessment, not an eligibility decision by OpenAI.

## What the program asks for

The form invites maintainers of active open-source projects and weighs usage, adoption or ecosystem importance, alongside maintenance work. It does not state a fixed star threshold. Benefits listed include six months of ChatGPT Pro with Codex, conditional Codex Security access and API credits for project work. Applications are reviewed on a rolling basis. Meeting basic application conditions does not guarantee selection.

## Evidence and gaps

| Signal | Observed evidence | Assessment |
|---|---|---|
| Public open source | Public repository; Apache-2.0 recognized by GitHub | Present; corrected an inconsistent MIT label in the synthetic data card |
| Maintainer activity | Recent implementation, tests, one merged same-repository PR (#1) | Present but a short public history; not evidence of external review |
| Reproducibility | Six passing Linux/macOS Python 3.11–3.13 jobs on f6f5b61; each 364 unit + 6 integration tests | Stronger engineering evidence; offline/synthetic scope only |
| Usability | Bilingual beginner README, temporary demo, bundled skill and contributor guide | Available; not proof that a beginner has independently succeeded |
| Public adoption | 0 stars, 0 forks at review; downloads not established | Main gap; cannot be repaired by wording |
| Release history | No published GitHub releases at review | Repository distributions exist; no release history claimed |
| Ecosystem importance | Recovery checks and reusable regressions address uncertain Codex submissions | Plausible contribution, not yet demonstrated ecosystem dependence |
| Privacy/security | Security guidance, synthetic fixtures, conservative recovery and local defaults | Present; no verified private reporting channel currently available |
| Live compatibility | Native Windows unsupported; live Desktop takeover and universal telemetry unverified | Explicit limits; not certified by offline tests |
| Repository presentation | About was empty | Description, README homepage and eight factual topics saved and verified through GitHub API in this update |

About, topics, a license badge, release tags and bilingual documentation are useful presentation aids, not stated program selection requirements. The evidence of actual use and maintenance matters more.

## Best honest application strategy

1. Lead with the concrete problem: after an uncertain submission, blindly repeating work can repeat side effects. Explain the reusable safeguards and link the tests that exercise them. Avoid presenting CRG as an official fix for Codex, unlimited context, or automatic Desktop rollover.
2. Separate existing evidence from the proposal. Existing: local tooling, conservative recovery and isolated CI. Proposed: bounded live compatibility experiments funded by support. Report negative results too.
3. Make review easy: use the short [form answers](FORM-ANSWERS.md), [review packet](REVIEW-PACKET.md), demo and one exact CI run. Do not overwhelm the 500-character fields with roadmap labels.
4. The most valuable next evidence is an independent maintainer reproducing the demo or reporting a real, sanitized failure. Request feedback only through an authorized outreach effort; do not manufacture stars, contributors, endorsements or usage statistics.
5. Prepare a versioned release after a separate release decision, with compatibility limits and reproducible artifacts. This can improve installation and traceability but does not establish adoption by itself.
6. Measure any claimed benefit using a preregistered baseline and a small authorized pilot. Until then, omit saved-token percentages, productivity multipliers and calibrated forecast claims. Existing synthetic replay is not a live outcome study.

It is reasonable to apply now as an early-stage project with a clear proposed contribution, or strengthen independent-use evidence first. The latter would address the weakest part of the current case; there is no verified acceptance probability or guaranteed way to maximize it.

## Suggested use of support

Use Codex for reviews, reproducible bug fixes, tests, documentation and release preparation. Use API credits only for bounded synthetic compatibility/bug-reproduction pilots whose outputs become reusable offline regressions. Start with a small capped pilot; estimate further credits from observed cost rather than inventing a large budget. Security review would be most relevant to path traversal, symlinks, permission checks and ambiguous recovery boundaries.

No application was submitted, no identity/organization fields were filled, no release was published and no credits were consumed during this review. Existing maintainer edits in APPLICATION-DRAFT.md and EVIDENCE.md were preserved; the new form answers supplement them with current public evidence.
