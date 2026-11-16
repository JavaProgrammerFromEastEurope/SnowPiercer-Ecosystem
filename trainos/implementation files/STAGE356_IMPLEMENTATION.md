# Stage 356 — Financial Transaction Boundary

## Objective
Validate a single invariant at the TrainOS financial command-ledger boundary.

## Contract covered
An execution identity cannot be bound to two idempotency keys.

## Verification
The corresponding test is in `tests/stage356/test_stage356_transaction_boundary.py`. Passing this test establishes only the stated local SQLite contract; it does not establish external payment-provider correctness or production readiness.
