# Stage 216 — Reconciled not-executed command requires a new reservation generation

## Scope

Adds a focused regression test for the local SQLite command idempotency and reconciliation ledger. This stage verifies existing contract behavior and does not expand external execution permissions.

## Verification scenario

- Reconciled not-executed command requires a new reservation generation.
- Rejected operations must not silently mutate persisted state.

## Safety boundary

These local tests do not authenticate external evidence, prove exactly-once physical execution, guarantee power-loss durability across all filesystems, or certify TrainOS for safety-critical deployment.
