# Stage 263 — Financial Ledger Contract

## Scope

Completed reconciliation stores durable evidence and dispatch generation.

This stage adds a focused regression test for the existing SQLite command idempotency ledger. It does not change the external execution adapter or establish production payment readiness.

## Verification target

`tests/stage263/test_stage263_ledger_contract.py`
