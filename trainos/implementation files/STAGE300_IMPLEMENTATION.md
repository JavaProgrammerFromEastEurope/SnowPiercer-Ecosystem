# Stage 300 — Financial Ledger Contract

## Scope

A completed command cannot transition back to UNKNOWN.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage300/test_stage300_ledger_contract.py`
