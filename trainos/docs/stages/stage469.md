# Stage 469: Timezone-equivalent timestamp comparison

## Goal
Confirms that timestamps expressed with different offsets are compared as instants, avoiding false ordering failures.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage469/test_stage469_audit_timestamp_timezone_order.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
