# Financial Ledger Contract v9 — External integrity checkpoints

Date: 2026-10-24

## Scope

This stage adds an external HMAC-SHA256 checkpoint for a validated, standalone SQLite ledger backup. The signing key is supplied by the caller and is not stored in SQLite or in the manifest. This is an additive prototype; existing TrainOS financial APIs remain unchanged.

## API

- `create_checkpoint(database, manifest_path, key_id=..., signing_key=...)` validates the database, hashes the exact database file, and writes a canonical JSON manifest atomically.
- `verify_checkpoint(database, manifest_path, keyring=...)` checks the trusted key ID, verifies the HMAC using constant-time comparison, checks the exact database-file digest and size, then revalidates database consistency.
- Key rotation is caller-managed: publish a new checkpoint using a new `key_id`; retain old verification keys only for as long as old manifests must remain verifiable. During overlap, pass both trusted keys in `keyring`.

## Threat model and limits

This mechanism detects changes to the database or manifest after checkpoint creation, including an attacker who edits database rows and recalculates database-local fingerprints, provided the attacker does not control the external signing key and cannot replace both the database and its trusted checkpoint reference. It does not protect against compromise of the signing key, malicious rollback to an older correctly signed checkpoint, or replacement of both artifacts and the trusted keyring. A caller should store keys in a secrets manager/HSM and pin checkpoint digests or versions in a separately protected system.

Use a closed standalone backup produced by `FinancialLedger.backup_to()` rather than hashing a live SQLite database with WAL sidecars. The HMAC is a shared-secret MAC, not a public-key digital signature. It authenticates only the exact file bytes and declared metadata; it is not a substitute for authorization, access controls, external settlement reconciliation, operational backup retention, or independent security review.

## Verification

- Financial ledger and legacy adapter tests: 53 passed.
- Targeted TrainOS tests for stages 172–177: 15 passed.
- `compileall`: see build manifest.
- Static AST scan: see build manifest.
- Full TrainOS test suite: not run.

## Status

`experimental / isolated prototype`. Not approved for real-money transactions. SnowPiercer integration remains gated on full-suite CI, key management and rollback policy, access-control design, accounting review, load qualification, and independent security review.
