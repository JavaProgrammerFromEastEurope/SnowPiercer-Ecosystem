# Stage 272 — Financial Ledger Contract

## Scope

NaN and infinite payload numbers are rejected before mutation.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage272/test_stage272_ledger_contract.py`
