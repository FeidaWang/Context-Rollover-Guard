# Contributing

Thanks for contributing to Context Rollover Guard.

Please keep changes conservative and explicit about their runtime assumptions. In particular, do not add behavior that retries an ambiguous mutation, exports task content by default, or claims automatic Codex Desktop switching without verified support.

Before opening a pull request, run:

```sh
python3 scripts/verify_offline.py --clean
```

Keep generated local state, archives, credentials, and machine-specific evidence out of commits. Add or update tests for behavioral changes, and describe any Codex-version dependency in the pull request.

Start with the [contributor quickstart](docs/CONTRIBUTOR-QUICKSTART.md) and [compatibility matrix](docs/COMPATIBILITY.md).


The documented command is implemented in v0.1.0. Use Python 3.11+; the hosted
matrix verifies Linux/macOS, not native Windows or a live Codex account.
Start with `python3 scripts/demo_offline.py` for a disposable offline walkthrough.
See [bounded first tasks](docs/GOOD-FIRST-ISSUES.md), the sanitized-fixture issue
form, and the [maintainer checklist](docs/MAINTAINER-CHECKLIST.md).

Keep public projections separate from private recovery content. Updating a fixture
requires provenance, synthetic identities, a manifest hash/size update and an explicit
consumer test. Regex scans alone do not prove that a dataset is safe to publish.
Do not submit a sensitive security report publicly; read [SECURITY.md](SECURITY.md).
