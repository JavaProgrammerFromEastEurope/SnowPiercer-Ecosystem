# Stage 336 — Reject non-standard NaN payloads

## Contract

NaN is rejected as invalid JSON input before the ledger is mutated.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage336/test_stage336_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
