# Synthetic timing dataset v1

Status: public-code synthetic benchmark asset; no real contributor data collected.
License: repository MIT license. Provenance: hand-authored numeric generator at
`benchmarks/datasets/generate.py`, using the reviewed typed interchange projection.
Reproduction creates new bundle/cluster/record aliases; identical hashes are not
expected across bundles. No local account IDs, prompts, answers, native logs,
paths, tools or credentials are read. Human-subject consent is not represented or
implied: all 150 records in five clusters are synthetic.

Distribution: 30 constant, 30 tiny, 30 abrupt shift/return, 30 gradual shift, and
30 heavy-tail tasks. Target is wall milliseconds. Tokens, active time, acceptance
time, quota and actual model/runtime measurements are null/unknown. No real model
or future-model availability is asserted. Negative/drift/tail cases are retained.
There are no experimental treatment benefits or measured real-world savings.

Use `sequence_index` for prefix-only training followed by scoring; never randomly
split records and claim chronological performance. Keep `cluster_id` groups separate
for project-held-out evaluation; repeated events are not independent tasks. Five
synthetic shapes are not representative of software projects or a user's personal
history. This asset is for interoperability/regression examples, not personal
forecast calibration or evidence of adoption.

Future real contributions are opt-in only: contributors must review the exact
sanitized export and license/consent statement, identify missingness and selection,
and receive a release-bundle ID. Do not accept raw logs. Withdrawal requests remove
the contribution from future releases and publish a tombstone/correction; already
copied public artifacts cannot be guaranteed erased. No real-data publication or
upload is authorized by generating this synthetic asset.
