# Local release construction

Use a Python 3.11+ interpreter (`python3 --version` first). The runtime and the
unified `python3 scripts/build_release.py` entrypoint require only the standard
library. `scripts/build_zipapp.py` invokes the same complete build. No upload,
installation, Git commit, or installed skill modification occurs.

Maintained skill text lives in the real `skills/context-rollover-guard/` directory.
The plugin manifest discovers the generated `dist/` skills after a build; this
avoids shipping an unbuilt source skill without its runtime. Do not install the
maintained source directory directly. Both PYZs, portable ZIP, pure Python wheel,
source tarball and manifests are staged and verified before any output is replaced.
Manifests are replaced last; interrupted multi-file publication is detected by
`python3 scripts/build_release.py --verify`. This is not an atomic directory swap.

`crg/__init__.py` is the version authority. Setuptools reads it dynamically; the
plugin's declarative version is a checked mirror. All artifacts contain LICENSE.
The wheel follows PEP 427 with hashed RECORD entries and console-script metadata;
the sdist contains the source and pyproject metadata for optional setuptools
builds (`setuptools>=68`, separate from the dependency-free runtime). Rebuilding
that sdist with an independently installed setuptools backend is not part of the
stdlib builder's byte-identity claim.

Set `SOURCE_DATE_EPOCH` explicitly for releases. The fallback is the fixed epoch
1700000000, not wall-clock time. ZIP member dates are 1980-01-01 with fixed POSIX
modes and sorted stored entries. Tar members use the epoch, zero owner IDs and
fixed modes; gzip has no filename and zero timestamp. Byte reproducibility is
scoped to identical inputs, Git provenance, epoch, Python and compression toolchain.
It does not promise cross-toolchain hashes. A dirty working tree is recorded.

`python3 scripts/check_release.py` extracts the final ZIP and wheel into a new
temporary directory and exercises the packaged CLI there. It does not load source
checkout modules. The skill self-test uses synthetic events only. `--verify`
compares every packaged core file and build provenance, validates the complete
inventory, and scans inputs and artifacts for forbidden state paths, absolute home
paths and common credential signatures. The signature scan is deliberately limited;
it cannot establish that arbitrary content is secret-free. Only reviewed source,
metadata and skill inputs are included, never private runtime evidence.

Native Desktop, installed hook behavior, Windows, hosted CI and live models require
separate evidence. A local artifact PASS does not establish those contracts.
