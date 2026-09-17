# Maintenance plan

Keep safety-sensitive changes in focused reviews. Every release should regenerate all distribution artifacts, verify source and artifact hashes, run clean-checkout offline gates, and record any narrowly required live compatibility test separately.

Schema/runtime changes trigger a fresh version-bound capability probe and review of unknown fields. New model IDs never imply capability. Existing transaction journals remain immutable and unknown future state schemas fail closed.

Use the compatibility-report template for contributor reproductions. Validate sanitized fixtures against a stated runtime version without requiring private author-machine files. Add external evidence only with permission and a stable public reference.

Prioritize: unknown-outcome recovery; native continuation coexistence; tool/child quiet-point evidence; scoped usage provenance; reproducible builds; private-data boundaries. Treat prediction accuracy and advanced selection as gated research until completed production observations exist. Do not train on unchosen-model counterfactuals or synthetic benchmark success.

Application submission, public publishing, live credit use, and external communications remain separate explicit actions.
