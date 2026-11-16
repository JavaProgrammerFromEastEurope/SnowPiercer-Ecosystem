# Stage 315 — Financial Ledger Contract

## Scope

A bound command cannot be completed without the matching execution identity.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage315/test_stage315_ledger_contract.py`
