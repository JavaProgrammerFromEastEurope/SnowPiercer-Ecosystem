# Stage 309 — Financial Ledger Contract

## Scope

Reusing an idempotency key for a different command name is rejected without mutating the original record.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage309/test_stage309_ledger_contract.py`
