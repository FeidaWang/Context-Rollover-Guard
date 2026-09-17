# Maintainer review checklist

- Identify the changed behavior, source commit, affected runtime contract and evidence grade.
- Preserve exact original bytes, workspace binding, permissions and no-blind-replay behavior.
- Verify defaults remain disabled; installing a skill must not install or trust hooks.
- Keep analytics independent from recovery authority and pending transaction storage.
- Review fixture provenance, synthetic identifiers, consumer coverage and manifest hashes.
- Inspect public changes for task content, native logs, personal paths, credentials and account identifiers; signature scans are only one check.
- Run `python3 scripts/demo_offline.py` for README/setup changes (implemented v0.1.0).
- Run `python3 scripts/verify_offline.py --clean` for default offline verification (implemented v0.1.0); distinguish audit mode from hosted OS isolation.
- Review Linux/macOS Python 3.11–3.13 results and final artifact checks at the exact commit; retain failures and verify fixes.
- Distinguish push, same-repository PR and real fork PR evidence. Never promote one to another.
- Keep English/Chinese README feature, privacy and activation claims equivalent.
- Confirm a private security-reporting route actually works before linking it as available.
- Keep live model calls, release publication, reset credits and real-data export outside default CI; require their separate scoped authorization.
- Record any unmet acceptance item instead of marking a gate passed from authored code alone.
