# Stage 328 — Completion requires the matching execution ID

## Contract

A bound command cannot be completed without its execution ID; rejection leaves the ledger unchanged.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage328/test_stage328_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
