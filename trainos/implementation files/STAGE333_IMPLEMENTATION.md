# Stage 333 — Enforce unique execution identity

## Contract

A second idempotency key cannot claim an execution ID already bound to another key.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage333/test_stage333_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
