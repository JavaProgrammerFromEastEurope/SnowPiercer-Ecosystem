# Stage 357 — Financial Transaction Boundary

## Objective
Validate a single invariant at the TrainOS financial command-ledger boundary.

## Contract covered
A repeated claim does not reset an existing dispatch reservation.

## Verification
The corresponding test is in `tests/stage357/test_stage357_transaction_boundary.py`. Passing this test establishes only the stated local SQLite contract; it does not establish external payment-provider correctness or production readiness.
