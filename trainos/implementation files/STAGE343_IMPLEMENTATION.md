# Stage 343 — Preserve generation during not-executed reconciliation

## Contract

Explicit evidence resets the reservation state while retaining the prior dispatch generation.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage343/test_stage343_ledger_contract.py` and `AUDIT/v43_*` verification reports.
