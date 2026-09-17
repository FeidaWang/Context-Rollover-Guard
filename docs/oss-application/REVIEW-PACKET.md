# Maintainer review packet — offline scope

This supplements the existing narrative draft without overwriting maintainer edits.
Submission and approval remain outstanding; no credit amount is requested here.
Private form fields (email, organization ID) must be supplied by the maintainer
outside this public repository. The official form was reviewed on 2026-09-18: each narrative answer allows 500
characters. Use the current [field-specific answers](FORM-ANSWERS.md) and
[eligibility review](ELIGIBILITY-REVIEW.md); recheck before submission.

## Project description (background, not a complete form answer)

Context Rollover Guard provides conservative local recovery and content-free usage analytics for long-running Codex work. It preserves exact handoff bytes, avoids blind replay after uncertain submissions, and checks public distribution artifacts offline. Our current evidence covers synthetic protocol tests and isolated Linux/macOS CI. Live account adapters, calibrated productivity gains, and independent adoption are not yet established.

## Review evidence

- [Support matrix](../COMPATIBILITY.md) separates verified and unsupported surfaces.
- [Public CI run on f6f5b61](https://github.com/FeidaWang/Context-Rollover-Guard/actions/runs/35257618983): six Linux/macOS jobs; each 364 unit + 6 integration tests and three artifact smoke checks. This verifies that commit, not subsequent edits.
- [CI policy](../ci-policy.md) and [source workflows](../../.github/workflows/ci.yml).
- [Reproducible demo](../../scripts/demo_offline.py) and [offline evaluations](../evaluations/summary.md).
- [Maintenance plan](MAINTENANCE-PLAN.md), [bounded credit methodology](API-CREDIT-PLAN.md), and [privacy](../privacy.md).
- Distribution files are repository artifacts; no new hosted release is claimed.

Shipped local behavior: explicit recovery, offline replay, normalized imports,
scoped status and previewable exports. Experimental: local statistical forecasts
and injected reset adapters. Unverified: live account contracts, native Windows,
future runtime compatibility, live savings and externally consented trials.

## Technical release-post draft (not posted)

The local analytics path now separates context pressure, observed token usage and
provider quota. Numeric observations and revisions use an independent SQLite
ledger with durable cursors and explicit unknown baselines. Imports are bounded,
exports require an exact preview, and recovery remains conservative when remote
acceptance is uncertain. Reproduce the offline demo and tests before enabling
experimental adapters; please report unsupported cases using synthetic fixtures.

## Feedback and maintenance

Triage reports by runtime/platform and source evidence; request sanitized numeric
fixtures, reproduce failures offline, preserve negative results, and add regression
coverage before changing support claims. Spend any separately granted credits only
on bounded compatibility regressions and verified bug reproduction. Do not create
inference traffic for monitoring, promotion or benchmark volume.
