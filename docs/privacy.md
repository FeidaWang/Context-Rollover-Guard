# Analytics and recovery privacy

Recovery archives intentionally retain exact private prompt/answer bytes. Analytics
stores separate allowlisted numeric observations; it is never recovery authority.
POSIX directories use 0700 and SQLite/key/export files use 0600. WAL/SHM inherit the
private database boundary. Permissions are not encryption. Local disks only are
verified; native Windows ACL/durability support is unverified.

There is no background collection, automatic upload, retention sweep or destructive
statistics cleanup command. Retain analytics until the owner explicitly chooses to
remove a closed analytics database and its sidecars. Never remove a recovery journal
or an open database to repair an analytics error. Unresolved recovery data remains
inspectable regardless of whether analytics is enabled.

`local_identity` creates a random local HMAC key for caller-supplied identities;
the key is private and never exported. Do not use an email or raw account identifier
as an analytics account ID. Export aliases are regenerated for each preview and
never include the persistent identity mapping. Numeric metadata may still identify
activity; do not call these bundles anonymous.

`export-preview` prints a bounded typed projection without arbitrary model/source
strings, prompts, answers, paths, tool output, authentication data or raw logs.
Review its exact JSON, save it privately, then use `export-write` with the displayed
SHA-256. A changed preview requires a new approval. Files are exclusively created;
existing files are never overwritten. Sharing/upload/publication needs separate
consent. Legacy/unknown export schemas fail closed.
