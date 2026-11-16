# Stage 341 — Block dispatch while outcome is unknown

## Contract

An UNKNOWN command cannot be dispatched again until explicit reconciliation.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage341/test_stage341_ledger_contract.py` and `AUDIT/v43_*` verification reports.
