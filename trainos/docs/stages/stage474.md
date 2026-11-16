# Stage 474: Concurrent independent backups

## Goal
Checks that concurrent backups to separate destinations both validate successfully.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage474/test_stage474_concurrent_distinct_backups.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
