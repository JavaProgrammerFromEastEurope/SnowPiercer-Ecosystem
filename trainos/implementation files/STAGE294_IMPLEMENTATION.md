# Stage 294 — Financial Ledger Contract

## Scope

Blank reconciliation evidence is rejected without changing UNKNOWN state.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage294/test_stage294_ledger_contract.py`
