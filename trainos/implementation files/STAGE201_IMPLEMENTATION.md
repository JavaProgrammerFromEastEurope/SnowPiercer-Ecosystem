# Stage 201 — Blank command identity is rejected before creating a ledger row

## Scope

Adds focused regression coverage for the local SQLite command idempotency and reconciliation ledger.

## Verification scenario

- Blank command identity is rejected before creating a ledger row.
- Verifies rejected operations do not silently mutate persisted state.

## Safety boundary

These local tests do not authenticate external evidence, prove exactly-once physical execution, guarantee power-loss durability across all filesystems, or certify TrainOS for safety-critical deployment.
