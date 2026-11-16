# Stage 280 — Financial Ledger Contract

## Scope

Execution-ID uniqueness holds across independent store instances.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target


tests/stage280/test_stage280_ledger_contract.py
