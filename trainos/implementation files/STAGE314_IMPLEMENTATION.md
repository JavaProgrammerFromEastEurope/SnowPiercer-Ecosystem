# Stage 314 — Financial Ledger Contract

## Scope

Explicit not-executed reconciliation permits a new dispatch generation exactly after evidence is recorded.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage314/test_stage314_ledger_contract.py`
