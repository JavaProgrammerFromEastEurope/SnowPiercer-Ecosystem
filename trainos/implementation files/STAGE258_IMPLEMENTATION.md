# Stage 258 — Financial Ledger Contract

## Scope

Equivalent command payloads with reordered JSON keys return the original claim.

This stage adds a focused regression test for the existing SQLite command idempotency ledger. It does not change the external execution adapter or establish production payment readiness.

## Verification target

`tests/stage258/test_stage258_ledger_contract.py`
