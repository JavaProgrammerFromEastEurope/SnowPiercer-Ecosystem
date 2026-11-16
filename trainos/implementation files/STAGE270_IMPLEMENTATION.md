# Stage 270 — Financial Ledger Contract

## Scope

Nested JSON object key order is canonical for claim fingerprints.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage270/test_stage270_ledger_contract.py`
