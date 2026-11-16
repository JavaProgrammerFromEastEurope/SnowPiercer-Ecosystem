# Stage 327 — Financial Ledger Contract

## Scope

Corrupt persisted fingerprints are rejected when reading a ledger record.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage327/test_stage327_ledger_contract.py`
