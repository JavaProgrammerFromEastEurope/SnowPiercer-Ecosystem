# Stage 302 — Financial Ledger Contract

## Scope

Not-executed reconciliation stores its evidence and dispatch generation durably.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage302/test_stage302_ledger_contract.py`
