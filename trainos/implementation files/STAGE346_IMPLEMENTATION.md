# Stage 346 — Reject stale not-executed evidence after a later dispatch

## Contract

Evidence used for a prior generation cannot authorize a later generation.

## Implementation

This stage adds a focused regression test against the existing `CommandIdempotencyStore` contract. No external provider or real payment operation is invoked.

## Verification

See `tests/stage346/test_stage346_ledger_contract.py` and `AUDIT/v43_*` verification reports.
