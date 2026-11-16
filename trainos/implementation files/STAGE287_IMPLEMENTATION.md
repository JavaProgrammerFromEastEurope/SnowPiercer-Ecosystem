# Stage 287 — Financial Ledger Contract

## Scope

Corrupt persisted result JSON is detected on read.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target


tests/stage287/test_stage287_ledger_contract.py
