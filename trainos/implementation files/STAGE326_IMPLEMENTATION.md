# Stage 326 — Financial Ledger Contract

## Scope

Execution binding diagnostics count a valid binding and return zero for an unrelated identifier.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage326/test_stage326_ledger_contract.py`
