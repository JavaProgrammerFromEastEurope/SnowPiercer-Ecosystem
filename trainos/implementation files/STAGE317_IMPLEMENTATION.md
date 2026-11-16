# Stage 317 — Financial Ledger Contract

## Scope

Completed reconciliation writes a durable audit entry that survives reopening SQLite.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage317/test_stage317_ledger_contract.py`
