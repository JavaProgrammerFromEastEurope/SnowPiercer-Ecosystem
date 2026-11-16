# Stage 260 — Financial Ledger Contract

## Scope

Blank execution identifiers are rejected before any ledger mutation.

This stage adds a focused regression test for the existing SQLite command idempotency ledger. It does not change the external execution adapter or establish production payment readiness.

## Verification target

`tests/stage260/test_stage260_ledger_contract.py`
