# Advice without execution authority

Legacy `recommend` remains an unverified preview. `recommend_verified` additionally
requires verified modality/tool/permission/context/risk capability projections,
then applies operator quality/cost rankings. A cheap model without a required tool
is excluded. Missing candidates return UNKNOWN. Cold-start ranks are heuristics,
not success probabilities or measurements of monetary prices. Histories remain
observational and do not establish causal superiority.

`accepted_workflow_cost` includes failed workflows in cost per accepted task and
keeps tokens, wall time, percentage points and money as separate units. Zero
accepted tasks or missing unit evidence yields null. The caller must supply the
whole workflow including repair/recovery work, one record per task, and external
acceptance evidence. No scalar utility or automatic paid exploration is enabled.

All recommendations default to one agent and require current-runtime execution
resolution. They do not change models, permissions, tools, hooks or credits.
`presentation` binds status to an unchanged task/policy and preserves exact raw
answer bytes and hashes. An owned UI may place its separate block before a declared
conclusion; JSON/code/native surfaces use a separate status surface. Native skill
placement remains best effort, not a Stop-hook rewrite API. Missing advice never
triggers another model turn. Status UTF-8 bytes are measured; tokenizer use is null.
