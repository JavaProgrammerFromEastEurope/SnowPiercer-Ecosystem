# Stage 277 — Financial Ledger Contract

## Scope

Not-executed evidence cannot be reused after a later dispatch generation.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage277/test_stage277_ledger_contract.py`
