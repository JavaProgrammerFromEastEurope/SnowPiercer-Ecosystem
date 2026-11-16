# Stage 468: UTC-normalized audit timestamp ordering

## Goal
Rejects a later audit sequence whose timestamp is earlier than a preceding event when timestamps are normalized to UTC.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage468/test_stage468_audit_timestamp_order.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
