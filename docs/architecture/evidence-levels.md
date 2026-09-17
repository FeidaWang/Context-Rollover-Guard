# Evidence levels

Evidence describes a scoped observation, never automatic permission to execute.

| Grade | Meaning | Does not prove |
|---|---|---|
| `synthetic` | Hand-authored fixtures, mocks, fake transports, deterministic replay; also labeled OFFLINE_TEST | Installed protocol compatibility, account availability, Desktop behavior, actual task quality or savings |
| `recorded-sanitized` | A real recorded event reduced with reviewed provenance and consent; include original runtime/surface and transformation | Current compatibility, completeness, or permission to replay a mutation |
| `schema-only` | Installed version-bound generated schema was inspected/validated | Authentication, authorization, successful execution or end-to-end behavior |
| `live-verified` | An authorized real operation was observed under specified source/runtime/model/effort/account mode/surface and test conditions | Other versions, surfaces, accounts, future availability or universal correctness |
| `unverified` | Plan, static hypothesis, absent or insufficient evidence | A passing test, compatibility, adoption or performance |

Static source inspection is a method, not a live evidence grade. Artifact hash/CRC checks establish byte integrity; they do not establish runtime behavior. A locally executed build/self-test is distinct from a hosted CI run or public release. Historical receipts remain historical even if source code is unchanged.

Each report should record source commit/fingerprint, command, exit status, discovered/passed/failed/skipped counts where applicable, time, interpreter/platform and evidence grade. Preserve negative results and unknowns. Scope binary/schema evidence to the executing runtime, not only the creation version of a resumed transcript. No installed runtime was invoked for CRG-1001.

Synthetic fixture strings resembling model IDs, identities or runtime versions are test data. `verified_real` in an invented unit-test object exercises a branch; it does not convert that object into real evidence. Public fixture provenance is in `tests/fixtures/manifest.json`.

No public artifact may contain raw recovery archives, captured prompt/answer content, credentials or personal paths. Local file permissions are not encryption. Field allowlists and human inspection complement pattern checks; neither a passing regex check nor a SHA-256 digest establishes consent or trust.
