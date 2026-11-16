# Stage 320 — Financial Ledger Contract

## Scope

Blank uncertainty reasons are rejected before state mutation.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage320/test_stage320_ledger_contract.py`
