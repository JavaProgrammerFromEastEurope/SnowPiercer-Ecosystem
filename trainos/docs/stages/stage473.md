# Stage 473: Backup destination failure cleanup

## Goal
Checks that a missing destination parent is rejected before any temporary backup file is left behind.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage473/test_stage473_backup_destination_failure_cleanup.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
