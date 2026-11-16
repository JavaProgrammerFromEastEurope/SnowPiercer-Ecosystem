# Stage 431: Reject an incomplete backup schema

## Contract

A SQLite file without the ledger table is rejected.

## Verification

Covered by `tests/stage431/test_stage431_backup_recovery.py`.
