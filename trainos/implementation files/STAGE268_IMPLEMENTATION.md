# Stage 268 — Financial Ledger Contract

## Scope

An unbound claim cannot reserve external dispatch.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage268/test_stage268_ledger_contract.py`
