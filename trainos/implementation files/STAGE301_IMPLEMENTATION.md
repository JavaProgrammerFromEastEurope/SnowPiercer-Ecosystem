# Stage 301 — Financial Ledger Contract

## Scope

Repeated reconciliation of an already completed command is idempotent.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage301/test_stage301_ledger_contract.py`
