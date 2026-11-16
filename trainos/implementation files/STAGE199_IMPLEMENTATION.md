# Stage 199 — Reusing an idempotency key for another command is rejected

## Scope

Adds focused regression coverage for the local SQLite command idempotency and reconciliation ledger.

## Verification scenario

- Reusing an idempotency key for another command is rejected.
- Verifies rejected operations do not silently mutate persisted state.

## Safety boundary

These local tests do not authenticate external evidence, prove exactly-once physical execution, guarantee power-loss durability across all filesystems, or certify TrainOS for safety-critical deployment.
