# Stage 325 — Financial Ledger Contract

## Scope

Completed reconciliation stores explicit evidence and the dispatch generation in durable audit.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage325/test_stage325_ledger_contract.py`
