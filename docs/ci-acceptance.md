# Hosted offline acceptance evidence

Verified source: `272a2c6c140b03bd222c8716d8b4a4db7f4fb84d`.

- [Push run 35252402408](https://github.com/FeidaWang/Context-Rollover-Guard/actions/runs/35252402408): six jobs succeeded.
- [Same-repository PR run 35252406382](https://github.com/FeidaWang/Context-Rollover-Guard/actions/runs/35252406382): six jobs succeeded.
- [PR #1](https://github.com/FeidaWang/Context-Rollover-Guard/pull/1).

Each push job ran 324 unit tests and 4 integration tests with no failures or skips,
built and verified final artifacts, and passed three out-of-tree artifact smoke checks.
The runner reported `os_network_verified: true` in every job. Counts overlap across jobs.

| Platform | Actual Python patch versions |
|---|---|
| Linux | 3.11.16, 3.12.14, 3.13.15 |
| macOS | 3.11.9, 3.12.10, 3.13.15 |

Commands are defined in `.github/workflows/ci.yml` and invoke
`python scripts/verify_offline.py --clean --network-policy=os` under Linux network
namespace isolation or macOS sandbox-exec network denial. The selected interpreter,
empty HOME/CODEX_HOME and credential-free child environment are documented in
[CI policy](ci-policy.md). The local focused command
`python3.13 -m unittest tests.unit.test_offline_runner -v` passed four tests.

## Retained failures and scope

- [Initial run 35251819136](https://github.com/FeidaWang/Context-Rollover-Guard/actions/runs/35251819136): macOS passed; Linux failed at inherited sysfs interface enumeration.
- [Run 35251998878](https://github.com/FeidaWang/Context-Rollover-Guard/actions/runs/35251998878): macOS passed; Linux failed the route-table assumption.
- [Diagnostic run 35252247759](https://github.com/FeidaWang/Context-Rollover-Guard/actions/runs/35252247759): confirmed an empty Linux route file, not a populated route table.

The final probe uses current namespace interface enumeration and per-thread routes,
accepts empty/header-only routes, and still rejects extra interfaces, populated or
malformed route data, successful connections and unexpected socket errors.

This is hosted synthetic/offline evidence. A same-repository PR is not a fork PR.
Cross-repository fork acceptance, manual release workflow, live model/hook/Desktop
compatibility and native Windows remain unverified. No live model was called.
