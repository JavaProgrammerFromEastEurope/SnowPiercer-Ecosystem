# Stage 335 — Reject non-JSON payloads atomically

## Contract

Non-JSON-serializable payloads are rejected before any idempotency record is created.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage335/test_stage335_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
