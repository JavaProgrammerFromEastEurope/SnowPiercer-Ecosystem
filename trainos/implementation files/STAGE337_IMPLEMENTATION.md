# Stage 337 — Verify completed record durability

## Contract

A completed record and its canonical result survive closing and reopening the SQLite database.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage337/test_stage337_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
