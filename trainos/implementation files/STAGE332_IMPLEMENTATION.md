# Stage 332 — Require UNKNOWN before not-executed reconciliation

## Contract

A merely CLAIMED command cannot be reconciled as not executed without a recorded UNKNOWN outcome.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage332/test_stage332_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
