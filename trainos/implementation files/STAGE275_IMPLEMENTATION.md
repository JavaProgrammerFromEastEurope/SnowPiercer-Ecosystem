# Stage 275 — Financial Ledger Contract

## Scope

A completed command cannot transition back to unknown.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage275/test_stage275_ledger_contract.py`
