# Stage 279 — Financial Ledger Contract

## Scope

Reusing an idempotency key for a different payload preserves the original claim.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target


tests/stage279/test_stage279_ledger_contract.py
