# Stage 366 — Transaction Boundary

## Objective
Two concurrent store instances produce exactly one dispatch reservation winner.

## Test
`tests/stage366/test_stage366_transaction_boundary.py`

## Limits
This test validates the local SQLite ledger contract only. It does not prove external provider behavior, distributed exactly-once execution, PCI compliance, or production payment readiness.
