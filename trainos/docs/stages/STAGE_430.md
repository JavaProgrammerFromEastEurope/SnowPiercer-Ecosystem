# Stage 430: Reject unsupported backup schema versions

## Contract

A snapshot with a future user_version is not accepted.

## Verification

Covered by `tests/stage430/test_stage430_backup_recovery.py`.
