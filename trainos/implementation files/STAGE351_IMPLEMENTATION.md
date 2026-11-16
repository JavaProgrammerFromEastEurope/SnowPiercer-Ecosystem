# Stage 351 — Financial Transaction Boundary

## Objective
Validate a single invariant at the TrainOS financial command-ledger boundary.

## Contract covered
A conflicting idempotency-key reuse is rejected without mutation.

## Verification
The corresponding test is in `tests/stage351/test_stage351_transaction_boundary.py`. Passing this test establishes only the stated local SQLite contract; it does not establish external payment-provider correctness or production readiness.
