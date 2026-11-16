# Stage 360 — Transaction Boundary

## Objective
Repeating the same UNKNOWN reason is idempotent; a conflicting reason is rejected.

## Test
`tests/stage360/test_stage360_transaction_boundary.py`

## Limits
This test validates the local SQLite ledger contract only. It does not prove external provider behavior, distributed exactly-once execution, PCI compliance, or production payment readiness.
