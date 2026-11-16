# Stage 304 — Financial Ledger Contract

## Scope

Dispatch reservation is refused after command completion.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage304/test_stage304_ledger_contract.py`
