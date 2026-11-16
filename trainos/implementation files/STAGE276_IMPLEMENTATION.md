# Stage 276 — Financial Ledger Contract

## Scope

Repeated completed reconciliation does not duplicate its audit row.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage276/test_stage276_ledger_contract.py`
