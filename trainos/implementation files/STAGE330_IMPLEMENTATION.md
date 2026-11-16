# Stage 330 — Prevent COMPLETED to UNKNOWN transition

## Contract

A completed result remains authoritative when a later timeout report attempts to mark it UNKNOWN.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage330/test_stage330_ledger_contract.py` and the v42 verification reports in `AUDIT/`.
