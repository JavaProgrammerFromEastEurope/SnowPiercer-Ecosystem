# Stage 339 — Make dispatch reservation single-use per generation

## Contract

A second reservation attempt cannot create a second dispatch reservation for the same generation.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage339/test_stage339_ledger_contract.py` and `AUDIT/v43_*` verification reports.
