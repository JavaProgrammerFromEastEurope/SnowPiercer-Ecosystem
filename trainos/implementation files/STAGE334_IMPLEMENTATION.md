# Stage 334 — Preserve execution binding on repeated claim

## Contract

A repeated claim with the same key and payload cannot substitute another execution ID.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage334/test_stage334_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
