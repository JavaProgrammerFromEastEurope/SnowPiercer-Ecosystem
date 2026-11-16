# Stage 312 — Financial Ledger Contract

## Scope

Blank idempotency keys and command names are rejected before ledger mutation.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage312/test_stage312_ledger_contract.py`
