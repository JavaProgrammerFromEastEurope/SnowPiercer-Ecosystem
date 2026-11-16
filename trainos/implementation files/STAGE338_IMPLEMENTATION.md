# Stage 338 — Require execution identity before dispatch

## Contract

Dispatch reservation returns false for an unbound command and does not mutate its dispatch fields.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage338/test_stage338_ledger_contract.py` and `AUDIT/v43_*` verification reports.
