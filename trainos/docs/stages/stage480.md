# Stage 480: Audit Blob Evidence

## Goal

Blob evidence rejected.

## Acceptance criteria
- The backup validator reports a diagnostic for malformed audit data or schema.
- Validation is read-only and does not repair or silently accept malformed history.
- Valid local SQLite snapshots continue to pass the established checks.

## Test
`tests/stage480/test_stage480_audit_blob_evidence.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or provider/payment safety.
