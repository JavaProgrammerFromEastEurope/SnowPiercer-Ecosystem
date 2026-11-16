# Stage 90 — Checkpoint-bound recovery and bounded attempts

## Changes

- Recovery attempts now persist the SHA-256 fingerprint of the exact backup checkpoint and a maximum attempt count. Existing Stage 89 databases are migrated in place with compatible defaults.
- Startup recovery fingerprints the backup before beginning a journaled attempt and passes the expected fingerprint to restore.
- Backup restore checks the expected fingerprint before copying and verifies the source fingerprint again after the SQLite copy, rejecting a backup that changed during the operation.
- Retry authorization can explicitly bind to a reviewed checkpoint fingerprint. A retry with a different fingerprint is blocked without consuming the authorization.
- The maximum-attempt limit is persisted with the attempt record; a caller cannot raise it by passing a larger value on a later attempt. Once exhausted, a new attempt key is required after review.
- Added tests for checkpoint-bound authorization, bounded retries, recorded backup fingerprints, and changed-backup rejection.

## Validation

- Full test suite: **655 passed** in 3.63 seconds.
- Focused Stage 86–90 tests: **24 passed** in 0.43 seconds.
- `python -m compileall -q kernel tests`: passed.
- AST parse across `kernel` and `tests`: **2,569 Python files, 0 parse errors**.

## Limitations

SHA-256 identifies the file bytes but does not authenticate who supplied the backup. A local attacker able to modify both the backup and attempt journal may bypass these application-level controls. The recovery workflow remains non-destructive and does not promote a candidate into the active database. This is not a safety-certified train-control component.
