# Stage 305 — Financial Ledger Contract

## Scope

Invalid completion JSON is rejected before state mutation.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage305/test_stage305_ledger_contract.py`
