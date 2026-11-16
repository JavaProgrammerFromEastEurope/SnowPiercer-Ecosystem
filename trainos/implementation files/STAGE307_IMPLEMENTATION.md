# Stage 307 — Financial Ledger Contract

## Scope

Concurrent dispatch reservation across independent stores has exactly one winner.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage307/test_stage307_ledger_contract.py`
