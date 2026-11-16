# Stage 291 — Financial Ledger Contract

## Scope

Invalid non-JSON payloads are rejected before a ledger row is inserted.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage291/test_stage291_ledger_contract.py`
