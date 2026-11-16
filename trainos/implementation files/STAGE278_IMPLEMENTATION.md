# Stage 278 — Financial Ledger Contract

## Scope

Required identity normalization is idempotent across repeated claims.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target


tests/stage278/test_stage278_ledger_contract.py
