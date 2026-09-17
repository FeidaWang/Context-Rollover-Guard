# Hook failure and live experiment policy

## Public hook behavior

Repository and CLI adapters have no verified current-session blocking contract.
They do not enable prompt or precompaction interception, regardless of configured
mode or historical evidence. A failed valid Stop emits one JSON systemMessage and
exit 0, so diagnostic/capture failure does not request another assistant answer.
Other failed events emit one JSON diagnostic and exit 1. Exit 1 is **not** proof
that a runtime blocked input. Invalid/oversized input with unknown event is also
exit 1; it is never guessed to be a Stop. Normal successful outputs are unchanged.

Failure codes: CRG_STORAGE_FULL, CRG_PERMISSION_DENIED, CRG_HOOK_TIMEOUT, and
CRG_CAPTURE_UNCONFIRMED. Diagnostics contain no exception text, prompt or answer.
They instruct the operator to retain originals and recovery records and inspect
local state before any retry; failure is never authority for mutation replay.

The internal dispatcher can produce a blocking JSON decision only when a caller
already supplies the verified blocking contract and guarded policy. Failures in
prompt capture or state inspection remain blocking under that contract, without
claiming that input was saved. Public adapters continue to supply false. Synthetic
unit tests of this branch do not establish a live contract. External process kills
and runtime-enforced hook timeouts cannot be caught by Python; interception must
remain disabled until that runtime's timeout/exit/stdout semantics are verified.

## Artifact input boundaries

POSIX reads traverse parents with descriptor-relative O_DIRECTORY/O_NOFOLLOW,
pin the final parent inode, reject nonregular leaves before open, open with
O_NOFOLLOW/O_NONBLOCK, and compare inode/device before and after open. Files must
belong to the current uid; private CRG artifacts must have no group/other bits.
Lock files use the same pinned-parent, no-follow and regular/owner/private checks,
with a 4 KiB limit; a bounded local creation race is reinspected before locking.
State reads cap at 16 MiB; generic private artifacts cap at 256 MiB. Native
transcripts cap at 256 MiB total and 1 MiB per line, also when growing. Oversized
or unsafe inputs are unavailable evidence, never SAFE. Transcript session, source
root and workspace checks remain in place; historical versions confer no current
execution authority. No recovery records are deleted.

This is a local POSIX filesystem contract. It does not protect against hostile
same-uid processes, hard-link aliasing by that uid, malicious filesystems, or
privileged attackers. Descriptor pinning prevents a parent symlink substitution
from redirecting a read; an already opened inode can still be modified by an
actor with write permission. Write-side directory replacement by the same uid
is outside this boundary. Windows, network filesystems and installed runtime
behavior remain unverified. Larger artifacts previously accepted without a cap
now require explicit review rather than an unbounded read.

## Live experiments: disabled until a reviewed bounded adapter exists

All nine historical model/Desktop live entrypoints and direct LiveServer
construction (including command_only) now raise
CRG_LIVE_DISABLED_UNVERIFIED_CONTRACT before reading real HOME, creating fixture
files, installing hooks or launching a process. This is an intentional loss of
legacy live-test availability, not a claim of successful live validation. The
read-only tests.live_schema inspector is exempt: it only reads supplied schema
files and cannot launch a runtime or model.

There is no CLI flag, environment variable or self-asserted evidence file to
re-enable these runners. Explicit user authorization is necessary but insufficient
without an implementation enforcing all of:

- Selected model and maximum calls, counting manual compaction and retries.
- Enforceable token or monetary limit, not merely post-hoc usage observation.
- A total run deadline and documented cancellation/retention behavior.
- Exact effective hook inventory from the current runtime for every source,
  matched against a separately reviewed allowlist before thread creation;
  unknown, extra, disabled or untrusted entries abort. No trust bypass.
- A typed export allowlist excluding prompts, answers, native logs, paths,
  credentials and stable account identifiers.

The offline exact-inventory validator tests this prerequisite; no active live
runner currently consumes its output because all legacy runners are disabled.
Dead historical experiment bodies remain as design references, not supported
ways to launch tests. Reactivation requires a separately reviewed adapter and
explicitly authorized run; removing only the entry guard is unsafe.

Request-acceptance timeout means UNKNOWN, not rejected. Observation timeout means
completion was not observed, not that work stopped. The separately authorized
total deadline limits the experiment's observation/launch policy; it must not be
misrepresented as a remote hard spending cap. Preserve unresolved request intent
and reconcile positive evidence; never resubmit to finish a slow test.

Default test discovery uses test_*.py. Offline verification additionally uses an
empty HOME/CODEX_HOME, allowlisted environment, no Codex on PATH, and a Python
audit guard rejecting real runtimes/network operations. OS network isolation is
not independently certified. No live/account, paid-model or Desktop checks were
run for this change; G1 remains pending.
