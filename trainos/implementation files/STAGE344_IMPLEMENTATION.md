# Stage 344 — Require execution binding for completed reconciliation

## Contract

A bound command cannot be reconciled without its matching execution ID.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage344/test_stage344_ledger_contract.py` and `AUDIT/v43_*` verification reports.
