# Stage 155 — execution command identity consistency

## Change

`ExecutionJournalConsistencyChecker` verifies that the latest execution audit
record's `command_id` matches the idempotency record's `command_name` before it
classifies the journals as consistent or authorizes dispatch. A mismatch is a
fail-closed `CONFLICT`; the checker is read-only and does not repair either journal.

## Tests

Added `tests/stage155/test_execution_command_identity_mismatch.py` for mismatched,
blank/corrupted, and suffix-conflicting command IDs; a matching identity control;
and a completed audit history that is internally valid but belongs to another command.

## Safety boundary

This is an application-level consistency check, not an atomic transaction across
both SQLite databases and not a guarantee of exactly-once external execution.
