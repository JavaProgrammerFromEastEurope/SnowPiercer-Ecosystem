# TrainOS Stage 80 — Verified anchor import and rollback-resistant checkpoint state

## Goal
Make portable signed integrity checkpoints useful during recovery by verifying them before import, persisting the trusted sequence monotonically, and comparing restored event history against both its internal hash chain and the independently retained checkpoint.

## Changes
- Added `EventIntegrityAnchorStore.import_signed_anchor(serialized, signing_key)`. It authenticates the exact JSON envelope using the Stage 79 HMAC verifier before storing the checkpoint.
- Imported checkpoints cannot lower the latest trusted event sequence. A different hash at the same sequence is rejected; re-importing the same sequence/hash is idempotent.
- `create_anchor()` refuses to create a checkpoint from a journal that already has hash-chain integrity findings, and refuses to replace a newer trusted checkpoint with a rolled-back journal.
- `verify_against()` now checks the journal's full internal hash chain as well as the stored trusted checkpoint. Findings include `event_store_integrity_failure` (with `integrity_code` preserving the underlying finding), anchor mismatch, missing anchored rows, and rollback cases.
- Added regression coverage for valid portable import, invalid signatures, checkpoint rollback, same-sequence conflicts, idempotent import, database rollback, and payload tampering that leaves the stored head hash unchanged.

## Verification
- Focused tests for Stages 76–80: 30 passed.
- Full test suite: 609 passed.
- `compileall`: see build verification for this archive.
- AST parse: see build verification for this archive.

## Security boundaries
- HMAC authenticates anchors only while the shared secret remains secret; it is not a public-key signature.
- The local SQLite anchor database must be protected separately from the event database. This stage does not implement remote transport, WORM storage, key rotation, or independent key management.
- Import authenticates and stores a checkpoint; callers must invoke `verify_against()` to compare it with the current event store before treating restored history as valid.
- This subsystem is not safety-certified and must not be treated as a train-control safety interlock.
