# Stage 295 — Financial Ledger Contract

## Scope

A previously used not-executed proof cannot authorize a later dispatch generation.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage295/test_stage295_ledger_contract.py`
