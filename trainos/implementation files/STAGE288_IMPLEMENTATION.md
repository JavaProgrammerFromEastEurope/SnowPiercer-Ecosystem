# Stage 288 — Financial Ledger Contract

## Scope

Repeated equivalent claims are read-only and preserve an existing dispatch reservation.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage288/test_stage288_ledger_contract.py`
