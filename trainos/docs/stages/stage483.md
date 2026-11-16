# Stage 483: Audit Invalid Decision

## Goal

Invalid decision type rejected.

## Acceptance criteria
- The backup validator reports a diagnostic for malformed audit data or schema.
- Validation is read-only and does not repair or silently accept malformed history.
- Valid local SQLite snapshots continue to pass the established checks.

## Test
`tests/stage483/test_stage483_audit_invalid_decision.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or provider/payment safety.
