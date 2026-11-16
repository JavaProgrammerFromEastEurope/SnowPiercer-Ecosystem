# Stage 298 — Financial Ledger Contract

## Scope

A completion request with a mismatched execution identity is rejected without changing the record.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage298/test_stage298_ledger_contract.py`
