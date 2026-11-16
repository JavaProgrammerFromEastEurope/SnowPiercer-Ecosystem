# Stage 342 — Block dispatch after completion

## Contract

A COMPLETED command cannot receive another dispatch reservation.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage342/test_stage342_ledger_contract.py` and `AUDIT/v43_*` verification reports.
