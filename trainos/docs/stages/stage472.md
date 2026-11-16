# Stage 472: Corrupt backup read failure

## Goal
Returns a validation finding for a file that is not a readable SQLite database.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage472/test_stage472_corrupt_backup_read_failure.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
