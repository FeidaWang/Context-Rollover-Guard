# Contributing

Thanks for contributing to Context Rollover Guard.

Please keep changes conservative and explicit about their runtime assumptions. In particular, do not add behavior that retries an ambiguous mutation, exports task content by default, or claims automatic Codex Desktop switching without verified support.

Before opening a pull request, run:

```sh
python3 scripts/verify_offline.py --clean
```

Keep generated local state, archives, credentials, and machine-specific evidence out of commits. Add or update tests for behavioral changes, and describe any Codex-version dependency in the pull request.

Start with the [contributor quickstart](docs/CONTRIBUTOR-QUICKSTART.md) and [compatibility matrix](docs/COMPATIBILITY.md).
