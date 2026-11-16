# Stage 471: Audit primary-key revalidation

## Goal
Rejects a backup whose reconciliation sequence column is no longer the primary key.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage471/test_stage471_audit_primary_key_recheck.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
