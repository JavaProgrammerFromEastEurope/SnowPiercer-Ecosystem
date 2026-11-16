# Stage 308 — Financial Ledger Contract

## Scope

A repeated claim with the same canonical command returns the existing record without creating a second claim.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage308/test_stage308_ledger_contract.py`
