# Contributing

Thanks for contributing to Context Rollover Guard.

Please keep changes conservative and explicit about their runtime assumptions. In particular, do not add behavior that retries an ambiguous mutation, exports task content by default, or claims automatic Codex Desktop switching without verified support.

Before opening a pull request, run:

```sh
python3 -m unittest discover -s tests/unit -v
python3 dist/context-rollover-guard/scripts/self_test.py
```

Keep generated local state, archives, credentials, and machine-specific evidence out of commits. Add or update tests for behavioral changes, and describe any Codex-version dependency in the pull request.
