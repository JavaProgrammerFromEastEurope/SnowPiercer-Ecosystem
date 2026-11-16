# Stage 267 — Financial Ledger Contract

## Scope

Legacy schema migration adds dispatch generation and backfills prior reservations.

This stage adds a focused regression test for the existing SQLite command idempotency ledger. It does not change the external execution adapter or establish production payment readiness.

## Verification target

`tests/stage267/test_stage267_ledger_contract.py`
