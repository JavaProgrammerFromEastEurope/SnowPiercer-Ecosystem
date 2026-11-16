# Stage 470: Duplicate reconciliation event detection

## Goal
Rejects repeated reconciliation events with the same idempotency key, dispatch generation, decision, and evidence.

## Acceptance criteria
- The validator rejects malformed or contradictory backup history without repairing it.
- Valid backup/restore operations preserve ledger and reconciliation state.
- Concurrency behavior does not silently overwrite an existing destination.

## Test
`tests/stage470/test_stage470_duplicate_audit_event.py`

## Verification boundary
These tests cover local SQLite behavior only. They do not prove off-host durability, distributed exactly-once execution, or disaster-recovery RPO/RTO.
