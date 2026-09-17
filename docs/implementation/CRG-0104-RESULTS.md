# CRG-0104 — Unified reproducible release build

Baseline re-read before implementation: local main `8079b5c3e87b0e74d79f56c3c3236060fc62cdc6`. The baseline build script was inspected; it still updated only the top-level pyz. Prior CRG-0101/0102/0103 changes are preserved. No remote-main freshness claim is made.

## Build and verify

Use Python 3.11+; `python3` below must resolve to a supported interpreter.

```sh
python3 scripts/build_release.py
python3 scripts/build_release.py --verify
```

The old `python3 scripts/build_zipapp.py` entry point now delegates to the complete release build. It no longer produces a partial release. No pip dependencies, network access, runtime authentication, or model requests are needed.

The builder captures one input snapshot containing all recursive `crg/` files/resources, `pyproject.toml`, build scripts, and skill source files. Python caches, bytecode, and `.DS_Store` are excluded; symlink members are refused. Generated files are excluded from the source fingerprint to avoid circular hashes.

It produces:

- `dist/crg.pyz`, using `#!/usr/bin/env python3`.
- `dist/context-rollover-guard/scripts/crg.pyz`, with identical bytes.
- `dist/context-rollover-guard/BUILD-INFO.json`.
- `dist/context-rollover-guard.zip`, containing the complete skill directory.
- `dist/MANIFEST.json` and `dist/context-rollover-guard.manifest.json`, with the same versioned metadata and artifact hash set.

Both manifests use a new `format_version: 1` envelope. Consumers of the old flat skill hash map must now read `artifacts`; its keys are relative to `dist/`. Manifests do not hash themselves, avoiding self-reference.

Embedded build metadata in the pyz and skill records package version, Python requirement, source commit, build-input dirty status, per-source hashes, aggregate source SHA-256, and UTC generation time. The repository currently declares version `0.1.0`; this ticket does not publish or increment a release. A dirty build records the actual input hashes and `source_dirty: true` rather than claiming the commit alone identifies the code. Temporary clean verification snapshots have their own synthetic Git commit and are not upstream commits.

`--verify` is read-only and exits nonzero for mismatched source fingerprints, differing manifests, missing/extra artifacts, hash corruption, pyz copy differences, missing/changed packaged source, package version disagreements, or ZIP/directory disagreement. It compares packaged source to the current source snapshot; it does not claim the current Git HEAD equals the recorded original build commit when source-equivalent history differs.

## Reproducibility and publication

To reproduce identical bytes, use the same input snapshot and Git provenance with a fixed timestamp:

```sh
SOURCE_DATE_EPOCH=1700000000 python3 scripts/build_release.py
```

Archive member ordering, timestamps, and permissions are fixed. ZIP members are stored without compression to avoid compressor-version differences. This increases archive size modestly but keeps the build stdlib-only. Without `SOURCE_DATE_EPOCH`, the generation timestamp changes, so byte-for-byte equality across builds is not expected.

All outputs and manifests are constructed and verified in staging before publication. Each destination is replaced atomically, with manifests last. This is not a filesystem-wide atomic transaction: an interruption during multi-file publication can leave a mixture. Verification rejects that mixture; rerun the explicit build to recover before distributing anything. It never reports a partially published release as valid.

## Acceptance and validation — OFFLINE_TEST

- [x] Recursive package/resource inclusion.
- [x] Identical top-level and bundled pyz bytes.
- [x] Complete skill ZIP regenerated.
- [x] Manifests generated from final artifact bytes, with matching metadata/hash sets.
- [x] Source commit/version/Python compatibility/SHA-256/timestamp recorded.
- [x] Portable Python shebang and skill commands; no Python 3.13 requirement introduced.
- [x] Explicit read-only verification command with failure exit status.
- [x] Reproducibility, corruption, version mismatch, source drift, staging failure, interrupted publication, and symlink tests.

`python3.13 scripts/verify_offline.py --clean` passed on macOS/Python 3.13.14 with isolated configuration, no ignored private evidence, and offline network/runtime guards:

- 185 unit tests passed, including 9 release tests.
- 2 CLI integration tests passed.
- Unified build and artifact verifier passed (10 hashed artifacts).
- Skill directory self-test and independently extracted ZIP self-test both passed.

Remote CI, Linux/Python 3.11–3.12 execution, and live runtime activation remain pending. No feature beyond CRG-0104 was started. The test/build scope does not establish live Codex compatibility or production activation.
