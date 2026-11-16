# Stage 297 — Financial Ledger Contract

## Scope

The execution-binding diagnostic detects duplicate bindings after index loss.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage297/test_stage297_ledger_contract.py`
