# Stage 266 — Financial Ledger Contract

## Scope

Dispatch reservation is durable and only increments generation once per attempt.

This stage adds a focused regression test for the existing SQLite command idempotency ledger. It does not change the external execution adapter or establish production payment readiness.

## Verification target

`tests/stage266/test_stage266_ledger_contract.py`
