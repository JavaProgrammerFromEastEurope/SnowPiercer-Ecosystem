# ISLAND-GEO-008: trust and crash protocol

Sequence: local lock -> reconcile external witness -> commit SQLite phase intent -> witness CAS -> commit local accepted row and remove phase. SIGKILL after intent means abort if witness unchanged; SIGKILL after witness CAS means replay the exact witness-committed record into local accepted. Any unexplained divergence fails closed. Witness CAS idempotent for the same committed head; it is **not** an authorization permit.

## Trust boundary

The witness MUST run under a distinct unprivileged UID with a separately owned directory, database and socket, while the client UID must not be able to modify witness storage. SO_PEERCRED authenticates Linux peer credentials but does not attest software integrity. `allowed_uids` controls access. Client-side code is not a mandatory production entrypoint. Root can replace both stores. Socket substitution and file-system rollback by privileged attackers require external protections and independent tests.

## Limits

No durable monotonic hardware witness, no full four-UID verification, no trusted IPC entrypoint wrapping legacy `ReplayLedger`, no fsync of parent directories, no anti-rollback for witness database itself, no independent cryptographic witness attestation. SQLite durability relies on storage/filesystem semantics. `recover` is fail-closed on divergent states; it does not prove malicious rollback impossible. NO-GO for physical deployment.
