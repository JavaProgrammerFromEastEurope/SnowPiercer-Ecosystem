# Stage 329 — Reject mismatched execution IDs

## Contract

Completion with an execution ID different from the stored binding is rejected without mutation.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage329/test_stage329_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
