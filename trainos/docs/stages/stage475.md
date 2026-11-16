# Stage 475: Concurrent no-overwrite publication

## Goal
Checks that competing store instances publishing to one destination have a single winner and leave no temporary files.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage475/test_stage475_concurrent_same_destination_no_overwrite.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
