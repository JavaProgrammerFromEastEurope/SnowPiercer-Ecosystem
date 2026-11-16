# Stage 313 — Financial Ledger Contract

## Scope

Dispatch cannot be reserved for a command without a bound execution identity.

This stage adds focused regression coverage for the existing SQLite command idempotency ledger. It does not introduce an external payment adapter or certify production execution safety.

## Verification target

`tests/stage313/test_stage313_ledger_contract.py`
