# Context Rollover Guard

[简体中文](README.zh-CN.md) · English

Context Rollover Guard (CRG) is an open-source Codex skill and Python runtime for handling long-running work safely when a context rollover is approaching or a prior handoff must be resumed.

It is deliberately conservative: it preserves the original task, records a durable handoff, and requires positive evidence before treating an uncertain operation as accepted. It never silently replays a prompt or claims that it has switched the active Codex Desktop task.

## What it does

- Runs a self-contained, dependency-free Python runtime on Python 3.11+.
- Inspects explicit project configuration, hook state, and existing recovery journals.
- Creates and verifies durable handoff archives when used by an authorized integration.
- Uses `tokenUsage.last.totalTokens` for active-context pressure when a supported runtime provides it; it never substitutes cumulative session usage.
- Stops safely on ambiguous acceptance rather than sending a duplicate prompt.

## What it does not do

- It does not install global hooks or background services when imported or tested.
- It does not provide universal token telemetry; that depends on the active Codex runtime and explicit project integration.
- It does not take over the currently open Codex Desktop task or switch the UI automatically.
- It does not resend a message, reset a journal, or archive an old task merely because a readback is missing.

## Install the skill

The portable skill lives in [`dist/context-rollover-guard`](dist/context-rollover-guard). Install that directory using your Codex skill or plugin workflow, then invoke it in a task as `$context-rollover-guard`.

For a local inspection before installing:

```sh
python3 dist/context-rollover-guard/scripts/self_test.py
python3 dist/context-rollover-guard/scripts/crg.pyz --help
```

The repository root also includes a Codex plugin manifest, so plugin-aware tooling can discover the bundled skill at `dist/`.

## First use

Ask Codex:

```text
Use $context-rollover-guard to run the offline self-test and report the result.
```

The self-test uses synthetic events in a temporary directory. It does not consume model usage, install hooks, or prove automatic Desktop switching.

To inspect a project:

```text
Use $context-rollover-guard to inspect this project's configuration, hooks, and handoff state.
```

To continue a saved handoff, create a new task in the same workspace and provide the exact path to its `handoff.md`. Keep the source task until the new task has safely taken over.

## Development

```sh
python3 -m unittest discover -s tests/unit -v
python3 scripts/build_zipapp.py
```

The root runtime is standard-library only. `pip` packaging is optional and declared in [`pyproject.toml`](pyproject.toml). Local journals, handoffs, test workspaces, and machine-specific evidence are intentionally excluded from Git.

## Safety model

CRG treats unknown outcomes as recovery work, not permission to retry. A recovery operation is read-only unless an already-authorized owning integration advances a positively verified transaction. This design is especially important for prompts that could have been accepted even when their result is not yet visible.

See the bundled skill references for operational guidance: [`desktop.md`](dist/context-rollover-guard/references/desktop.md) and [`recovery.md`](dist/context-rollover-guard/references/recovery.md).

## License

Released under the [Apache License 2.0](LICENSE).

## Contributing and security

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes. Report security issues privately as described in [SECURITY.md](SECURITY.md).
