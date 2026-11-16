# Stage 487: Recovery Corrupt Audit

## Goal

Recovery acceptance refuses corrupted audit without mutating file.

## Acceptance criteria
- The backup validator reports a diagnostic for malformed audit data or schema.
- Validation is read-only and does not repair or silently accept malformed history.
- Valid local SQLite snapshots continue to pass the established checks.

## Test
`tests/stage487/test_stage487_recovery_corrupt_audit.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or provider/payment safety.
