# Model and execution-capability registry

CRG-1005 adds runtime/account binding and conservative parameter preparation. It
performs no model selection side effect, account lookup, request submission or
inference. Existing catalogs remain usable for observation and non-actionable advice.

## Discovery and scope

`discover_models(request, schema, binding=None)` calls only `model/list`, and validates
every pagination request against the supported subset of the supplied runtime schema.
It bounds pagination, refuses repeated cursors, discards incomplete/conflicting pages,
and handles absent methods or effort metadata conservatively. Unknown response fields
are ignored; malformed known dimensions invalidate the catalog rather than inferring
capabilities. Returned IDs are never derived from names or migration hints.

`runtime_binding(schema, auth_mode=..., account_scope_id=..., client_surface=...)`
checks the CRG-1004 generation, current executable bytes, freshness and actual evidence
surface. It binds binary digest, execution version, schema-map digest, surface, auth
mode and opaque account scope. Account scope is a **trusted adapter input**, not an
identity proof produced by CRG. The adapter must independently establish and recheck
it; the registry does not read credentials, account files or authentication APIs.
The detached probe has no verified account binding and remains observation-only.
Unknown or changed scope refuses action preparation. Supplying arbitrary strings is
not a way to authenticate an account, grant authority or attach to Desktop.

`VERIFIED_CATALOG` means the supported catalog projection completed, not that model
execution was tested. `automatic_actions_allowed` is always false. Binding a complete
catalog does not enable automatic switching. Scope/binary checks repeat after pagination.

## Separate dimensions and exact parameters

`resolve_action` now requires a fresh bound catalog, the matching current runtime
schema/binding, and a caller-supplied already authorized turn envelope. It prepares
parameters only. Successful output contains separate internal dimensions:

- `model_id`: exact returned ID.
- `reasoning_effort`: exact catalog value also accepted by the action schema.
- `execution_mode`: currently `single_agent` only; never a wire effort field.
- `service_tier`: existing authorized tier, also explicitly exposed by the model.
- `permission_profile`: existing authorized profile, or preserved sandbox policy.

The resolver deep-copies the authorized envelope and changes only model/effort.
It preserves input text, workspace, approval policy, permissions, network/tool-related
settings and all other fields. A provider mismatch, changed tier/profile, unsupported
mode, malformed dimension or unsupported schema constraint refuses preparation.
The complete `turn/start` request is validated before returning `wire_params`.
No request is sent. The dispatching adapter must revalidate runtime, account scope,
authorization and freshness immediately before any later submission.

Both evaluation time and current wall-clock age must be within one hour of catalog
observation; `--at` cannot revive stale evidence. The separate CRG-1004 runtime-evidence
TTL still applies. Revision IDs include runtime/account binding and model capabilities;
changed metadata requires an explicit new decision. These digests detect consistency
changes; they are not signatures or protection against a malicious trusted caller.

## Names, migration and unknown windows

Display names (including Astra, Sol and Luna) are presentation only. A preference
for future GPT-6 Sol remains unverified and cannot resolve without an actual returned
ID and complete contract. There is no hard-coded future model ID, launch date, context
window or quota multiplier. `upgrade` is an informational hint, never an alias or
permission to migrate. `Ultra` is not mapped to an effort; even an exposed value is
refused if the action schema rejects it.

The compatibility field `context_window` represents catalog metadata only. It does
not populate `published_api_window`, `context_window_runtime`, `compact_limit_runtime`
or a compaction threshold. These remain null/UNKNOWN without independent evidence.
Model names never provide missing telemetry or native-continuity guarantees.

## CLI compatibility and advice

`resolve-model` still accepts the old catalog/model/effort/time arguments, but now
returns UNAVAILABLE (exit 2) without a complete execution contract. New optional inputs
are `--schema`, `--manifest`, `--binding`, `--authorized-params`, `--execution-mode`,
`--service-tier`, and `--permission-profile`. Schema/manifest use the CRG-1004 generation
layout. Scope and envelope files are explicit trusted-adapter projections, never
credential exports. Successful preparation is exit 0; invalid input remains exit 1.
The action's canonical effort key is now `reasoning_effort`; wire format remains
`effort`. No installed runtime is launched by this command.

Advice remains a local heuristic preview. It explicitly reports `actionable: false`,
`automatic_switch: false`, and single-agent mode. Candidate fields attempting to add
tools, agents, network, permissions or execution modes are refused. Advice does not
validate a live execution contract or bypass the resolver.

## Evidence limits

Tests use a generated synthetic contract derived from public fixtures, opaque synthetic
account labels and a local Python executable digest that is never launched as a model
runtime. No installed model catalog/account/effort contract has been verified here.
Missing real evidence stays UNKNOWN. Actual runtime integration and authentication
scope provisioning require a separately authorized host adapter; this registry does
not add one implicitly. Existing owned recovery/execution paths are preserved and
remain subject to their separate configuration/trust-boundary work in CRG-1006.
