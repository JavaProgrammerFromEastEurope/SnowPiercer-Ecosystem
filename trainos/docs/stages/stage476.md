# Stage 476: Repeated restore preserves UNKNOWN

## Goal
Checks that repeated backup/open cycles preserve UNKNOWN and do not authorize an implicit retry.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage476/test_stage476_unknown_repeated_restore_cycles.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
