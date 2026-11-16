# Stage 296 — Financial Ledger Contract

## Scope

UNKNOWN state and its reason survive a database close and reopen.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage296/test_stage296_ledger_contract.py`
