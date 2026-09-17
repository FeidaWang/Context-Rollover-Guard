# Offline CI and release evidence policy

The local command is `python3 scripts/verify_offline.py --clean`. Select Python
3.11+ first. It creates a disposable, allowlisted source snapshot, builds final
artifacts, runs all unit/integration regressions, checks hashes/private-input
signatures, and runs the actual exported skill ZIP/PYZ/wheel outside the checkout.
No Git commit is created. Source commit/dirty provenance is explicitly carried
into the disposable build; it is bookkeeping, never recovery authority.

The runner supplies empty HOME/CODEX_HOME, an allowlisted environment and a PATH
containing only the chosen Python and Git. It excludes account files, private
evidence, ignored files and symlinks, and does not launch live model entrypoints.
Audit mode uses the inherited Python network/process guard. This is not a security
sandbox for malicious code and cannot certify OS-level network isolation.

Hosted jobs require `--network-policy=os`: Linux enters an empty network namespace
then drops to the original runner user; macOS applies inherited sandbox network
denial. Before tests, an isolated Python (-I, without the audit hook) checks OS
denial; Linux also checks for loopback-only interfaces and no routes. Missing OS
support, unexpected errors and timeouts fail the job. Never fall back silently.
Action checkout and Python provisioning occur before this network boundary and
may use network. Default jobs run on GitHub-hosted disposable machines, not trusted
self-hosted machines. Fork PRs use `pull_request`, no repository/model secrets,
read-only contents permission and no persisted checkout credential. These measures
are defense in depth, not a claim that PR code cannot alter its own tests.

Actions are pinned to upstream commit IDs with a readable version comment:
- [checkout v4.2.2](https://github.com/actions/checkout/commit/11bd71901bbe5b1630ceea73d27597364c9af683)
- [setup-python v5.6.0](https://github.com/actions/setup-python/commit/a26af69be951a213d495a4c3e4e4022e16d87065)

Pins were checked against official release links; they preserve the existing major
versions, not a claim of latest-version or complete dependency security review.
Review upstream changes and runner/Node support before updating pins; record actual
hosted outcomes. Python minor versions are matrix targets; manifests record the
actual patch and zlib toolchain. No third-party dependency is installed for tests
or the stdlib release builder. Optional setuptools rebuilds are a separate workflow
and must pin/review their dependency set before claiming reproducible backend output.

The manual release workflow performs verification only. It has no write permission,
secret-bearing live job, upload or publication step. Release notes must identify
synthetic/offline evidence and separately list installed/live/Desktop evidence as
NOT_RUN unless real scoped results exist. No supported-platform/live badge is
created by authoring YAML. All required failures are fatal; no continue-on-error.

Crash and recovery regressions remain in normal discovery. Future ledger database
migration/crash cases belong in tests/integration/test_ledger_migrations.py once the
ledger task implements them; this is a reserved integration point, not a present test.
Live evaluation remains disabled. Re-enabling it requires a reviewed adapter with
model/call/token-or-cost/deadline/export limits, effective-hook checks, and separate
explicit authorization. Never add live secrets to untrusted PR jobs.

Current evidence (2026-09-18 local date): local macOS Python 3.11.15,
3.12.13 and 3.13.14 passed the process-scoped sandbox-exec network policy;
see docs/audit/ci-os-macos-3.*-final.json and corresponding logs. The earlier
nested-sandbox startup failure is retained and is superseded only for this
explicitly approved local execution outside the outer sandbox.

The previously hosted push run
[35226491499](https://github.com/FeidaWang/Context-Rollover-Guard/actions/runs/35226491499)
tested commit a3943f6b5287da7666851b519f4b2a8cd253e9f0 with the old runner:
five jobs succeeded and Linux/Python 3.13 failed (236 tests, five errors).
It does not test the current dirty snapshot or certify its OS policy. Its
posix_spawn guard incompatibility is reproduced locally and addressed by
turning off subprocess's posix_spawn optimization in the test-only guard;
direct os.posix_spawn stays forbidden. This uses an internal CPython switch,
so future interpreter upgrades must rerun the guard regression.

Current-snapshot hosted Linux/macOS matrix verification is pending on an authorized
test branch. The duplicate legacy offline.yml workflow was removed: ci.yml is
the single default offline workflow and requires OS-level network denial.
A real fork PR remains NOT_RUN: the supplied repository is the upstream and
no existing fork or organization was visible to the authenticated owner.
No hosted fork-PR acceptance is inferred from same-repository or local results.
