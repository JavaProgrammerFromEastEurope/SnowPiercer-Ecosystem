# Stage 310 — Financial Ledger Contract

## Scope

An execution identity cannot be attached after a command has already been claimed.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage310/test_stage310_ledger_contract.py`
