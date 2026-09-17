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
python3 scripts/build_release.py
python3 scripts/build_release.py --verify
```

The root runtime is standard-library only. `pip` packaging is optional and declared in [`pyproject.toml`](pyproject.toml). Local journals, handoffs, test workspaces, and machine-specific evidence are intentionally excluded from Git.

## Safety model

CRG treats unknown outcomes as recovery work, not permission to retry. A recovery operation is read-only unless an already-authorized owning integration advances a positively verified transaction. This design is especially important for prompts that could have been accepted even when their result is not yet visible.

See the bundled skill references for operational guidance: [`desktop.md`](dist/context-rollover-guard/references/desktop.md) and [`recovery.md`](dist/context-rollover-guard/references/recovery.md).

## License

Released under the [Apache License 2.0](LICENSE).

## Contributing and security

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes. Report security issues privately as described in [SECURITY.md](SECURITY.md).

## Safe configuration

A clean checkout is disabled (`enabled = false`, `mode = "auto"`); emergency prompt and compaction blocking are opt-in. Installing the skill does not install hooks. Guarding requires explicit enablement plus a separately configured, verified integration; setting `enabled` alone does not prove activation.

Keep machine-specific runtime paths in `$CODEX_HOME/context-rollover.toml` (default `~/.codex/context-rollover.toml`), under `[context_rollover]` as `codex_binary`. If absent, runtime probes discover `codex` through PATH. Repository values override user values; CLI overrides apply last.

Run `python3.13 -m crg config --workspace .` to inspect effective values and per-field `sources` (`default`, `user`, `repo`, `cli`). This reads only CRG settings, never Codex credentials, and does not probe or install anything. `--codex PATH` overrides the runtime path for this inspection. Python 3.11+ is required; use an appropriate interpreter on your system.

For all offline gates on a temporary clean Git snapshot of the current non-ignored source files:

```sh
python3.13 scripts/verify_offline.py --clean
```

This excludes ignored machine evidence, isolates HOME/CODEX_HOME, rejects network and live-runtime launches during verification, runs unit and CLI integration tests, then builds and verifies every release artifact and self-tests both the skill directory and an extracted ZIP. CI covers Python 3.11–3.13 on Linux and macOS. With `--clean`, builds run inside the temporary checkout and leave working-tree artifacts unchanged. Run `python3 scripts/build_release.py` to regenerate the working-tree release artifacts.

## Runtime paths and diagnosis

For a new workspace without `crg.toml`, `python3.13 -m crg init --workspace /path/to/project` creates disabled configuration only. Existing files are never overwritten. Inspect with `python3.13 -m crg doctor --workspace /path/to/project` (JSON), or add `--format human`. Ordinary diagnosis is read-only; hook trust, telemetry, and enabled-session activation remain unknown without fresh evidence.

Runtime cache and receipts now default beneath the configured state root, independently of the source checkout. Existing evidence needs explicit path configuration; `doctor --evidence PATH` remains available. See [CRG-0103 paths, status semantics, and migration](docs/implementation/CRG-0103-RESULTS.md) before changing an existing integration. `doctor --probe` is a separate explicit runtime operation, not part of installation or ordinary inspection.

Uninstall/revert instructions are next to installation steps in the [contributor quickstart](docs/CONTRIBUTOR-QUICKSTART.md). Preserve pending recovery journals; skill removal does not uninstall separately installed hooks.


### Experimental M4 evaluation

Offline `statistical-audit` and `resolve-model` commands, plus the injected-adapter reset transaction engine, are documented in [M4 contracts](docs/metrics/EXPERIMENTAL-M4.md). They do not activate an advanced policy or perform live reset redemption. See the [CRG-0301–0401 acceptance report](docs/implementation/CRG-0301-0401-RESULTS.md) for passing offline checks and outstanding real-data, runtime and Windows/attachment gates.
