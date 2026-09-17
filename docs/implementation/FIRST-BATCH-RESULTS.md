# First implementation batch — 2026-09-17

Scope: CRG-0101, then CRG-0102, as limited by the supplied implementation entry point. No later ticket started. Local main was re-read before each ticket and remained `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`; no target-code baseline drift was found. No remote-main freshness claim is made.

## CRG-0101 acceptance

- [x] Repository defaults disable guarding, prompt blocking, and compaction blocking; mode is auto and no binary path is embedded.
- [x] Machine-specific runtime paths documented as user-local configuration; missing binary uses PATH discovery.
- [x] Config command retains effective-value sections and adds per-field default/user/repo/cli provenance. An inspection-only CLI binary override demonstrates final precedence.
- [x] English/Chinese documentation distinguishes skill installation from explicit hook integration.
- [x] Named inert-default, import-side-effect, runtime-discovery, and emergency-opt-in tests pass, along with precedence/CLI coverage. Disabled hook dispatch is tested even with blocking flags present.

## CRG-0102 acceptance

- [x] Public minimal synthetic protocol schema with integrity manifest replaces private-schema prerequisites.
- [x] Public projected compaction events contain no transcript text; privacy tests constrain event fields/strings and scan fixtures for common credential/path patterns.
- [x] Repo-hook regression gets synthetic version evidence and separately verifies UNKNOWN behavior when evidence is missing.
- [x] Live schema inspection is separate and explicitly requires a supplied path.
- [x] CI workflow defines Linux/macOS and Python 3.11/3.12/3.13 jobs.
- [x] Clean snapshot verification runs unit suite, CLI integration, build, and self-test of fresh pyz bytes, with ignored evidence absent and HOME/CODEX_HOME isolated.
- [x] Python audit guards reject network and live runtime launches during verification; negative tests verify those guards. Read-only Git metadata and a synthetic stdio fixture server remain allowed. These are regression guards, not an adversarial OS sandbox.

## Measured results — OFFLINE_TEST

Command: `python3.13 scripts/verify_offline.py --clean`

Environment: local macOS, Python 3.13.14. The runner copies tracked and non-ignored new files into a temporary committed, initially clean Git checkout; it does not commit the working repository. Ignored evidence is absent.

- Unit suite: 163 passed.
- Offline CLI integration: 2 passed.
- Fresh-build staged skill self-test: PASS; synthetic final active-context count 30000.
- `git diff --check`: passed.

## Boundaries and deviations

- CRG-0101 focused tests passed before CRG-0102 began; the combined clean-checkout gate followed CRG-0102 because removing private evidence dependencies is that ticket's prerequisite work.
- The existing builder only emits the top-level pyz. Verification stages those fresh bytes in a temporary copy of the skill before self-test. Committed pyz/ZIP/manifests remain unchanged; unified release generation belongs to CRG-0104.
- The schema fixture is hand-authored and synthetic, not a live-schema compatibility claim. Runtime path refactoring remains CRG-0103 scope.
- Remote CI jobs, Python 3.11/3.12, Linux, Windows, and live Codex/Desktop activation have not been executed in this session. No model/account request, quota redemption, automatic model switching, hooks installation, or production state-machine change was performed.
- Work remains as reviewable local changes; no PR or release was published.
