# Stage 347 — Prevent duplicate reservations across store instances

## Contract

Two SQLite store instances cannot reserve the same dispatch generation twice.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage347/test_stage347_ledger_contract.py` and `AUDIT/v43_*` verification reports.
