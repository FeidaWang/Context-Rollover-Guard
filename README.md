# Context Rollover Guard

[简体中文](README.zh-CN.md) · English

**A handoff notebook for long Codex tasks.** Context Rollover Guard (CRG) is a community-built Python tool and optional Codex skill. It helps inspect saved recovery state, verify handoff files, and avoid repeating an operation whose outcome is uncertain.

Imagine helping someone build a big LEGO model. When a new helper takes over, they need the instructions, what is already finished, and what still needs checking. CRG provides tools for that handoff. It does **not** give Codex unlimited memory, and installing it does **not** automatically move your conversation to a new task.

## What can I use today?

| Your goal | What is available |
|---|---|
| Try it without connecting an account | A temporary, synthetic offline demo |
| Check a project's CRG setup | Read-only configuration and recovery diagnosis |
| Continue an existing handoff | Verify its archive, then resume in a new task in the same workspace |
| Review usage | Explicitly import supported numeric records; see the [analytics guide](docs/quickstart.md) |
| Automatically guard any Desktop conversation | Not currently supported; requires a separately verified integration |

**Requirements:** Python 3.11 or newer. Offline CI covers Linux and macOS with Python 3.11–3.13. Native Windows is unsupported; WSL is not independently certified. These are CRG's boundaries, not Codex's platform requirements. CRG is not an official OpenAI product.

## Start here: a safe demo

Download this repository using GitHub's **Code → Download ZIP**, extract it, and open the extracted folder. If you already use Git, you can instead run:

```sh
git clone https://github.com/FeidaWang/Context-Rollover-Guard.git
cd Context-Rollover-Guard
```

### If you use Codex Desktop

1. Open the downloaded repository folder as a local project in Codex Desktop.
2. Start a task in that folder and paste this request:

   ```text
   Read README.md. Check that Python 3.11+ is available, then run
   python3 scripts/demo_offline.py and explain the result simply.
   Do not install hooks or enable live integration.
   ```

3. Look for `result: PASS` in the command output. That means four offline checks succeeded: create disabled settings, read settings, diagnose the workspace, and preview hook configuration without installing it.

The Python demo makes no model/API calls and needs no Codex login. Asking Codex to run it still uses your normal Codex conversation allowance. If Python is missing, install Python 3.11+ using the [official Python downloads](https://www.python.org/downloads/), then retry.

### If you use a terminal or Codex CLI

A terminal is the app where you type commands. Open it in the downloaded repository folder, then run these one at a time:

```sh
python3 --version
python3 scripts/demo_offline.py
python3 dist/context-rollover-guard/scripts/self_test.py
```

The first command must report 3.11 or newer. The demo should report `PASS`; the self-test should finish successfully. Neither installs CRG into Codex. You can run them before installing Codex CLI. For Codex itself, follow the [official setup guide](https://developers.openai.com/codex/quickstart).

## Optional: let Codex use the skill

A **skill** is a small instruction folder Codex can read. The ready-to-install folder is [`dist/context-rollover-guard`](dist/context-rollover-guard); it includes the Python runtime.

In Codex, ask the skill installer:

```text
Use skill-installer to install the skill from
https://github.com/FeidaWang/Context-Rollover-Guard/tree/main/dist/context-rollover-guard.
If a copy already exists, stop and show me its location instead of overwriting it.
```

Check the proposed installation location before accepting it. Then select `context-rollover-guard` in your client's skill picker. In Codex CLI, use `/skills` or type `$context-rollover-guard`. If it is missing, restart Codex and check again. See [OpenAI's skill instructions](https://developers.openai.com/codex/skills) and our [manual installation/uninstall guide](docs/CONTRIBUTOR-QUICKSTART.md).

For the first request, say:

```text
Use the context-rollover-guard skill to run its offline self-test.
Then explain what passed and what remains unverified.
```

Installing a skill adds instructions and scripts. It does not install hooks, start a background monitor, or enable automatic recovery. A **hook** is a separate integration that runs code when an event happens; beginners do not need one for the demo.

## Check your own project

From this repository folder, run the following command. Replace `/absolute/path/to/your-project` with the real folder path; keep the quotes if it contains spaces.

```sh
python3 dist/context-rollover-guard/scripts/crg.pyz doctor --workspace "/absolute/path/to/your-project" --format human
```

`doctor` checks CRG's setup without enabling it. `UNKNOWN` means there is not enough evidence; it does not mean the guard is active. If you want a starter configuration, `init` creates a disabled `crg.toml` and refuses to overwrite an existing file:

```sh
python3 dist/context-rollover-guard/scripts/crg.pyz init --workspace "/absolute/path/to/your-project"
```

A **workspace** is your project folder. A **handoff** is a saved package describing work to continue. If an authorized integration has already created a handoff, open a **new task in the same workspace**, supply the exact path to `handoff.md`, and ask CRG to verify the archive before continuing. Keep the original task and recovery files until the outcome is confirmed. The demo does not create a handoff of your real conversation.

## Important limits, in plain language

- CRG starts disabled. Changing `enabled` alone does not establish a working integration. No public hook adapter is currently certified for prompt interception.
- If a message may already have been accepted, CRG stops to check rather than sending it again. This reduces duplicate-operation risk; it is not an exactly-once delivery guarantee.
- Codex handles its own context compaction. CRG cannot enlarge the context window or guarantee lossless recovery on every client.
- Context space, token usage, and account quota are different things. CRG does not automatically read all chats or your live account balance. Forecasts are experimental; missing evidence stays unknown.
- Recovery archives may contain exact prompts and answers. Keep them private. File permissions are not encryption. Nothing uploads by default. Public test data is synthetic.
- Uninstall using the same manager that installed the skill, or remove only your recorded manual copy. Preserve unresolved recovery files. Separately installed hooks need their own [receipt-based rollback](docs/CONTRIBUTOR-QUICKSTART.md).

## For contributors

The runtime uses only the Python standard library. To reproduce the offline suite and rebuild the repository's distribution files:

```sh
python3 scripts/verify_offline.py --clean
python3 scripts/build_release.py
python3 scripts/build_release.py --verify
```

The clean runner tests a disposable source snapshot. Its local Python network guard is not an OS sandbox; hosted CI separately verifies OS network isolation. Passing offline tests does not certify a live Codex session. See [recorded CI evidence](docs/ci-acceptance.md) and the [support matrix](docs/COMPATIBILITY.md).

- [Contributor quickstart](docs/CONTRIBUTOR-QUICKSTART.md) · [Good first contributions](docs/GOOD-FIRST-ISSUES.md)
- [Recovery details](dist/context-rollover-guard/references/recovery.md) · [Desktop boundaries](dist/context-rollover-guard/references/desktop.md)
- [Analytics walkthrough](docs/quickstart.md) · [Privacy](docs/privacy.md) · [Architecture](docs/architecture/native-cooperative.md)
- [Contributing](CONTRIBUTING.md) · [Security reporting](SECURITY.md)

Released under the [Apache License 2.0](LICENSE).
