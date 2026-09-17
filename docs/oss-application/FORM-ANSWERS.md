# Codex for OSS — paste-ready draft

Reviewed 2026-09-18 against the [official application form](https://openai.com/zh-Hans-CN/form/codex-for-oss/). This is a draft, not a submitted application. Recheck metrics, links, role and current form limits before sending. The three narrative fields each currently allow at most 500 characters. Counts below include spaces and punctuation, exclude headings, and use ASCII-only answer text.

## Identity and selections

| Field | Suggested entry / action |
|---|---|
| Family and given name | Enter your real application name privately; do not infer it from a display name. |
| Email | Enter the email associated with your ChatGPT account privately. |
| GitHub username | `FeidaWang`; verify the profile is public. |
| Repository | `https://github.com/FeidaWang/Context-Rollover-Guard` |
| Role | Primary maintainer, if you personally own the maintenance responsibilities described below. |
| API credits | Select if you intend to carry out the bounded experiments below. The open form already had this selected; this review did not change it. |
| OpenAI organization ID | Copy the correct organization ID privately from the form's official settings link; never use an API key or commit this value. |
| Codex Security | Select only if you want security review of archive paths, ownership, recovery boundaries and packaging, and can triage the findings. Access is conditional, not a promised entitlement. |

The first-person wording below requires the maintainer to confirm it describes their actual responsibilities. Do not claim independent adoption or paid experiments that have not happened.

## Why this repository qualifies (476/500 characters)

```text
CRG is an early-stage Apache-2.0 project for safer long-running Codex work. Its reusable handoff and recovery checks target uncertain submissions that could otherwise repeat operations. Six Linux/macOS CI jobs each pass 364 unit and 6 integration tests, including offline distribution checks. The repository currently has 0 stars and 0 forks; adoption is not yet established. Its proposed ecosystem value is a reproducible, local-first foundation for safer Codex integrations.
```

## How API credits would be used (461/500 characters)

```text
Use credits for small, explicitly authorized compatibility and bug-reproduction experiments on synthetic tasks. Compare handoff recovery with a baseline, test ambiguous acceptance and protocol changes, then turn failures into offline regressions. Set a spend cap before each pilot and record model/version, tokens, outcomes and limitations. Publish sanitized fixtures and reproducible reports. Monitoring and local analytics will not generate inference traffic.
```

## Anything else (480/500 characters)

```text
I maintain the runtime, skill packaging, tests and bilingual onboarding. CRG starts disabled and preserves recovery evidence when outcomes are unclear. Current validation is offline/synthetic; native Windows, live Desktop takeover and independent adoption remain unverified. Support would help convert reproducible failure cases into maintained compatibility tests. Review packet: https://github.com/FeidaWang/Context-Rollover-Guard/blob/main/docs/oss-application/REVIEW-PACKET.md
```

## Before submitting

1. Refresh the public metrics and point reviewers to the latest passing commit's CI run. Monthly downloads are unavailable, not zero.
2. Confirm the identity, role, organization and credit-use plan. Do not paste private logs or account identifiers into public evidence.
3. Read the linked current program terms and submit personally when ready. This preparation has not accepted terms or sent the form.

The strongest honest case is a narrowly defined maintenance problem plus reproducible evidence. No text can establish an acceptance probability; public adoption remains the main evidence gap. See [eligibility review](ELIGIBILITY-REVIEW.md) and [credit plan](API-CREDIT-PLAN.md).
