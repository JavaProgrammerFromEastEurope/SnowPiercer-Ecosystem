# Stage 265 — Financial Ledger Contract

## Scope

Dispatch reservation for a missing key fails closed and does not create records.

This stage adds a focused regression test for the existing SQLite command idempotency ledger. It does not change the external execution adapter or establish production payment readiness.

## Verification target

`tests/stage265/test_stage265_ledger_contract.py`
