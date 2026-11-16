# Stage 290 — Financial Ledger Contract

## Scope

Execution-ID uniqueness is enforced across independently opened store instances.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage290/test_stage290_ledger_contract.py`
