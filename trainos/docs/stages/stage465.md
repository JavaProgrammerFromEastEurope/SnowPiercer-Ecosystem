# Stage 465

## Purpose

465 existing backup is not overwritten.

## Contract

This stage verifies a focused backup/recovery safety property for the local SQLite command ledger. Invalid audit metadata must be rejected without silently repairing the snapshot; failed backup publication must not leave a final artifact or temporary file; idempotency state must survive backup/reopen cycles.

## Verification

Run the stage test with `pytest tests/stage465` from the TrainOS repository root.
