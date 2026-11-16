# Stage 340 — Preserve dispatch reservation after database reopen

## Contract

Reopening the database does not clear the durable reservation or reset its generation.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage340/test_stage340_ledger_contract.py` and `AUDIT/v43_*` verification reports.
