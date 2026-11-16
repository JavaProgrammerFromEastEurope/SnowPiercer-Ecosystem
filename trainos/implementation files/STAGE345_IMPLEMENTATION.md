# Stage 345 — Persist reconciliation evidence and dispatch generation

## Contract

The audit row records the evidence, decision, and generation associated with reconciliation.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage345/test_stage345_ledger_contract.py` and `AUDIT/v43_*` verification reports.
