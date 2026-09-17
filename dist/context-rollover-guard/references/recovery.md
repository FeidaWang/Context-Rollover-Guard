# Inspect an existing transaction

Run the bundled runtime with existing, explicit paths:

```sh
python3 <skill>/scripts/crg.pyz recover --workspace <absolute-workspace> --transaction-root <transactions> --archive-root <archives> --rollover-id crg_<digest>
```

Without --reconcile this inspects the journal without contacting Codex. Missing transactions are not permission to recreate them. A MODE_B handoff need not have an owned-client transaction; do not fabricate one.

Positive readback reconciliation is advanced integration work. It requires an external version-bound schema directory and the appropriate owning runtime; schemas are deliberately not bundled as portable evidence. Use --schema explicitly if proceeding under existing authorization. Never treat an absent readback as permission to resend. Unique clientId, exact prompt, and accepted turn provide positive forward confirmation. Do not reset state, delete claims, replay prompts or archive the old task to bypass ambiguity.
