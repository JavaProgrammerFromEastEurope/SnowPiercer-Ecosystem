# Stage 286 — Financial Ledger Contract

## Scope

Dispatch generation increments only after explicit not-executed reconciliation and a new reservation.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target


tests/stage286/test_stage286_ledger_contract.py
