# Stage 271 — Financial Ledger Contract

## Scope

Non-JSON payloads are rejected before creating a ledger record.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage271/test_stage271_ledger_contract.py`
