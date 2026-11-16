# Stage 303 — Financial Ledger Contract

## Scope

Dispatch reservation is refused while a command outcome is UNKNOWN.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage303/test_stage303_ledger_contract.py`
