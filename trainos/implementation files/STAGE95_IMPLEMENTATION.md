# TrainOS Stage 95 — Startup recovery restart idempotency

## Scope

Make startup recovery idempotent when a process restarts after a recovery candidate has already been published and the durable recovery-attempt journal has already committed `SUCCEEDED`, but the caller did not receive or persist the returned result.

## Implementation

- `EventLogStartupRecovery.run()` now recognizes an existing candidate for a journal entry in either `IN_PROGRESS` or `SUCCEEDED` state.
- Before reusing it, the startup path verifies that the current backup fingerprint matches the journaled checkpoint, independently verifies the backup and candidate against the anchor, and checks that their event and anchor sequence positions match.
- An interrupted `IN_PROGRESS` entry is finalized as success only after verification. A previously `SUCCEEDED` entry is reused without attempting to publish again.
- A tampered, mismatched, or untrusted candidate fails closed and is preserved for operator investigation.
- Existing finding code `interrupted_publication_reconciliation_failed` remains unchanged for the interrupted state to preserve the existing test/API contract. The already-succeeded state uses `recovery_candidate_reconciliation_failed` when validation fails.

## Tests

Added `tests/stage95/test_startup_recovery_restart_idempotency.py`:

1. Run successful recovery, close and reopen the journal (restart simulation), and rerun startup recovery with the same attempt key. The same verified candidate is returned without republishing, and the damaged active database is not promoted or changed by recovery.
2. A tampered candidate associated with a `SUCCEEDED` journal entry is rejected, preserved, and does not alter the terminal journal state.

## Validation

- Focused: `PYTHONPATH=. pytest -q tests/stage95 tests/stage91 tests/stage94` — 8 passed.
- Full suite: `PYTHONPATH=. pytest -q` — 669 passed.
- `python -m compileall -q kernel tests` — passed.
- AST audit of `kernel` and `tests` Python sources — 2,574 files, 0 parse errors.

## Limitations

Restart is simulated by closing and reopening the durable SQLite journal; this is not a physical power-loss or storage-controller test. A recovery candidate is never automatically promoted over the active database. The anchor and attempt journal remain local application-level controls, not tamper-proof external trust infrastructure. This stage does not certify TrainOS for real train control.
