# Capability evidence and resumed sessions

CRG-1004 separates cached runtime observations from authority over a current session.
All discovery remains opt-in (`doctor --probe`); loading configuration and cached
`doctor` inspection do not launch a runtime. Tests use synthetic offline runtimes only.

## Storage and publication

`context_rollover.evidence_root` resolves relative to the workspace (absolute paths
are also accepted). It defaults to `<state_root>/runtime`. The explicit
`schema_cache` and `capability_receipt` settings still override their individual
paths. `doctor --evidence-root PATH` overrides both for that command; `--evidence`
is its compatible alias. None of these paths derive from the package's `__file__`.

Each probe writes a new UUID generation under the schema cache, then atomically
replaces the complete capability receipt. Readers use only the generation referenced
by that receipt. A failed publication leaves the previous receipt intact; incomplete
or orphaned generations never authorize actions and are not automatically deleted.
Failed probes publish explicitly invalid evidence rather than silently using old success.

The manifest binds the resolved executable path, executable SHA-256, reported version,
actual `detached_cli` surface, checked timestamp, resolved schema-cache path and every
schema file's digest to one generation. The caller's requested surface is recorded
separately and cannot turn a detached probe into Desktop evidence. The binding digest
checks consistency, not authenticity against a malicious local writer. Schemas with
missing, extra, corrupt or path-escaping members are rejected. Evidence moved to a
different cache location must be regenerated.

Client startup validates the whole generation, executable bytes and reported runtime
version before opening its transport. A replaced executable is rejected even if its
version label is unchanged. A future timestamp or age above 24 hours is invalid for
action. This TTL is a conservative CRG policy, not a platform guarantee. Older bundles
may be inspected offline; legacy manifests cannot start a client. No evidence grants
hook blocking, automatic rollover, account permissions or UI ownership.

## Resume and observation

`session_meta.cli_version` is the session creation version. Repository hooks record
it as `session_creation_version`; they expose `current_execution_version: null` and
`current_runtime_status: UNKNOWN` because their payload lacks verified current-process
binding. Reading the configured executable or cached receipt cannot establish which
process currently owns Desktop. An old session after an upgrade therefore continues
safe exact-answer preservation, with historical numeric records explicitly marked
`OBSERVED_HISTORICAL_RECORD`. Such records are not fed to the active predictor.
Previously cached pending numeric samples/current context estimates are invalidated;
recovery journals, pending prompt/answer bytes and ambiguous acceptance are preserved.
Full incremental transcript ingestion remains a later task.

## Probe boundaries and verification limits

Metadata commands and isolated RPC use disposable HOME/CODEX_HOME and an allowlisted
environment. Hooks are enumerated only in a synthetic temporary project. RPC methods
are initialize/initialized, hooks/list, config/read and schema-validated read-only
model/list. No thread/turn creation, archive, reset or real hook trust change occurs.
The probe can hash existing configuration for inventory but does not rewrite it.

The offline runner exercises the same public fixtures in source, a temporary PYZ,
an extracted wheel-layout fixture and a disposable skill-style PYZ location. The
wheel and skill cases are layout fixtures, not backend wheel builds, pip installation
or a user skill installation. Python 3.13 has no setuptools in this environment;
the available system Python's setuptools 58.0.4 is below the declared build requirement.
No installation or network download is needed for these permitted layout checks.
Live Desktop behavior, installed wheel integration, Windows and OS network isolation
remain unverified. No real account or installed Codex was probed during this task.
