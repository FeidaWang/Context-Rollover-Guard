# Execution configuration and trust boundaries

CRG-1006 documents current behavior, not installed Desktop support. Settings affect
only the described adapters; configuration is intent, never evidence of capability.

## Every exposed CRG configuration setting

| Setting | Actual behavior |
|---|---|
| context_rollover.enabled | Defaults false. Public hook dispatch is inert and owned chat/session creation refuses while disabled. Explicit offline inspection remains available. |
| context_rollover.mode | auto/MODE_A/B/C are accepted capability-policy labels. Owned chat currently requires MODE_B plus reviewed trusted hooks; selecting a label does not grant a transport or interception capability. |
| context_rollover.codex_binary | Explicit runtime selection for probe/config/doctor. Executing AppServer binds to its verified schema receipt; it cannot silently substitute another binary. |
| context_rollover.state_root | Private mutable journals/telemetry root; default resolves under CODEX_HOME. Loading paths creates nothing. |
| context_rollover.archive_root | Private exact prompt/answer and handoff archive location; independent from native thread archival. |
| context_rollover.evidence_root | Default runtime evidence parent, workspace-relative or absolute. |
| context_rollover.schema_cache / capability_receipt | Individual evidence location overrides; CLI doctor --evidence-root overrides both. |
| context_rollover.hook_receipts | Reviewed installer-owned hook metadata location, not proof of active trust. |
| context_rollover.evidence_exports | Optional probe report destination; empty means no report export. |
| predictor.window_size | Bounds positive growth history used in the heuristic. |
| predictor.min_growth_tokens | Lower bound on estimated next-turn growth. |
| predictor.safety_buffer_tokens / safety_buffer_percent | Safety buffer is the larger token count or runtime-window fraction. |
| predictor.hard_arm_remaining_tokens | Additional low-headroom heuristic threshold. |
| predictor.derived_limit_percent | Caps derived/known-scope limit as a fraction of observed runtime window. |
| predictor.conservative_limit_percent | Lower conservative fraction when compaction scope/prefix is unknown. |
| predictor.warn_probability | Deprecated, accepted for compatibility and ignored with diagnostics; the score is not a calibrated probability. |
| rollover.archive_old_thread | Native archive RPC requires both durable preparation policy=true and current coordinator policy=true, positive forwarding receipt and a verified quiet point. False always suppresses new archive RPCs; local exact-content archives are still written. |
| rollover.preserve_model | Must be true. False now raises a controlled configuration error; changing an accepted/recovery operation's model is unsupported. |
| rollover.preserve_cwd / preserve_permissions / forward_original_prompt | Must be true; disabling any is rejected. Direct owned-session construction also validates these invariants. |
| emergency.block_auto_compact / force_rollover_on_next_prompt | Only potentially active under guarded_owned_rollover and verified adapter flags; public adapters currently provide no interception contract. Otherwise retained but inactive with diagnostics. |
| continuity.policy | observe: public hooks inert and owned execution refused. native_cooperative/manual_recovery: snapshots and explicit manual fresh-task routing, no automatic pressure-triggered rollover. guarded_owned_rollover: intent subject to capability gates, never an implicit permission grant. |

Offline analytics commands and low-level pure helpers are not disabled by the global
hook/chat switch. Their invocation is explicit and does not imply runtime mutation.
Direct Coordinator construction is a trusted embedded boundary requiring owned_surface;
it is not a replacement for validated application configuration.

## Durable archive policy and recovery

The prepared transaction records its archive policy. A later restart with a default
true flag cannot override an original false policy. A current false flag vetoes an
original true policy. Legacy journals lacking the field conservatively retain the
source. Existing receipts are not rewritten. If an archive was already accepted or
its acceptance is unknown, changing the setting cannot undo it: the existing receipt
or RECOVERY_REQUIRED state remains. Positive archived-list reconciliation may record
historical completion but sends no archive RPC. No recovery state is cleared to make
policy checks pass.

Guarantees are local deduplication, durable intent before submission, receipt ordering
and no blind resend after ambiguous acceptance. They are **not distributed exactly-once
delivery**. Source archival follows confirmed acceptance plus quiet-point evidence,
not a newly claimed universal completion guarantee. Disabling archival retains the
source even on the successful path. Receipt/status methods do not silently submit
pending prompts. Changing model advice does not change recorded transaction settings.

## Current instructions and exact content

Fresh thread creation no longer sets developerInstructions for recovery. The runtime
therefore reads its current developer/project configuration normally; archived text
and generic recovery boilerplate cannot replace it. The handoff index is returned as
separate result data. This intentionally removes automatic developer-channel injection
of the index; a caller/user must inspect the returned index through an authorized data
read. No attachment to native Desktop is implied.

Workspace archives include bounded, content-free fingerprints of root AGENTS.md,
AGENTS.override.md, .codex/config.toml, .codex/hooks.json and crg.toml. Absent files and
unsupported/symlink files are explicit ABSENT/UNKNOWN. These root-level fingerprints
are not a complete inventory of effective ancestor/nested/global/runtime instructions.
If a runtime response exposes developerInstructions, execution settings retain its hash
rather than replaying that text; an observed change or lost visibility refuses rollover
before forwarding. Unobserved developer state remains unknown. Fingerprints detect
change relative to a snapshot, not authenticity, authority or permission.

Prompt/answer text, Unicode, CRLF, empty strings and significant whitespace are retained
exactly. Unsupported non-text input and non-boolean fresh are rejected before a new
owned-input journal entry or request. JSONL chat rejects fields carrying attachments;
it does not forward just their text subset. Handoff shell text is data and is never
executed merely because it appears in an archive. Optional advice is emitted separately
and never modifies archived answers or live model/permission settings.

## Explicit owned execution

chat uses the runtime's existing configuration and no longer forces features.hooks=true.
The existing enabled/trusted/receipt-matching hook check must pass naturally. Startup
responses must preserve requested cwd/model/provider/approval/tier/profile/read-only
sandbox before input is accepted. An unsupported sandbox response is a controlled
failure, not permission widening. Resume/reconciliation reject --model/--permissions
overrides instead of silently ignoring them; use a separately authorized new task.
Fresh=true is explicit caller intent, never inferred from pressure or advisor output.

No global trust edits, hook installation, model calls or live validation were performed
for this task. Synthetic crash/reconciliation tests are not proof of current host hook,
Desktop, Windows or distributed exactly-once semantics. Hook I/O failure policy and
live-test isolation remain CRG-1007; actual rebuilt distribution is CRG-1008.
