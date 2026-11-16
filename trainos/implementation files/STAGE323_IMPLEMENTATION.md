# Stage 323 — Financial Ledger Contract

## Scope

Blank reconciliation evidence is rejected without changing the UNKNOWN record.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage323/test_stage323_ledger_contract.py`
