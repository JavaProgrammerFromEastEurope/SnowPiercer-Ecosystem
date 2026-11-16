# Stage 467

## Purpose

467 end to end backup audit validation and unknown.

## Contract

This stage verifies a focused backup/recovery safety property for the local SQLite command ledger. Invalid audit metadata must be rejected without silently repairing the snapshot; failed backup publication must not leave a final artifact or temporary file; idempotency state must survive backup/reopen cycles.

## Verification

Run the stage test with `pytest tests/stage467` from the TrainOS repository root.
