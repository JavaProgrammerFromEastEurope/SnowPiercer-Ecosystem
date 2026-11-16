# Stage 477: End-to-end recovery and audit validation

## Goal
Checks restored audit persistence and verifies backup validation is read-only.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage477/test_stage477_end_to_end_recovery_audit_readonly.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
