# Bounded first contributions

These are proposed tasks, not claims of completed external contributions. Each can
be submitted independently. Use synthetic data and describe the exact tested scope.

| Task | Scope | Acceptance |
|---|---|---|
| One protocol-drift fixture | Add one synthetic unsupported or missing field case to an existing capability test | Unknown capability remains unknown; no live process; manifest hashes and full offline suite pass |
| One timezone quota fixture | Exercise an explicit offset/reset boundary without an account | Keep quota buckets separate; do not infer a fixed token budget; add a regression and update the fixture manifest if applicable |
| One installation reproduction | Run the published offline demo and artifact verifier on a listed Python/OS pair | Report exact commit, interpreter, command, exit and evidence grade; omit local paths and account details; retain failures |
| One conservative error message | Improve one user-visible explanation for an unknown recovery outcome | Existing no-replay and exact-content tests still pass; do not change transaction state or permissions |

Before starting, check for duplicate work in the repository issues. A new platform
report is scoped evidence, not automatic support certification. Maintainers review
fixtures and privacy manually as well as running automated checks.
