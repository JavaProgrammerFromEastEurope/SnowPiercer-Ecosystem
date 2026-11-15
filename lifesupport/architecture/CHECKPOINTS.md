# LIFE-CORE-005 — Recovery Checkpoints & Trusted Journal Anchoring

## Scope
Offline logical lifecycle only. No physical device control, fail-safe certification, or operational readiness.

## Data flow
1. PersistentLifecycle replays and validates SQLite journal.
2. create_checkpoint writes a canonical JSON record with registry fingerprint, sequence, event hash and snapshot hash, authenticated using an independently held HMAC-SHA256 secret.
3. verify_checkpoint validates the HMAC and replays the anchored prefix. Journal extensions are allowed by default, but a shorter or rewritten anchored prefix is rejected.
4. create_backup uses SQLite backup API, verifies a full replay and emits an authenticated manifest with SHA-256 of the backup bytes.
5. restore_backup validates the backup before copying to a **new** destination using exclusive creation. Existing files are never overwritten.

## Trust assumptions and limits
- The HMAC key (at least 32 bytes) must be randomly generated and stored outside the database, backup, and anchor directory. Never commit it to version control.
- The anchor file needs independent, access-controlled storage. Replacing both the anchor and key defeats the protection. An attacker who can replace the anchor with an older *validly signed* anchor may still induce rollback; a remote monotonic counter or immutable external anchoring is not implemented.
- Backup manifest and backup file are two distinct outputs, not one atomic transaction. An interrupted backup may leave an unpaired artifact: operators must verify before use.
- Backup creation and verification assume no untrusted process concurrently changes the backup file. A full threat model for concurrent adversarial mutation is not provided.
- SHA-256 is not authentication; HMAC is used to authenticate the signed document. No encryption, secret management, remote attestation, or key rotation is implemented.
- An anchor can lag behind the journal. Unanchored tail events cannot be independently authenticated against an external head.
- A restored file is never activated automatically; integration, operational safety, and physical equipment remain NO-GO.
