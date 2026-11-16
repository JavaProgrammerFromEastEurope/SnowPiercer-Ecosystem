# Stage 197 — UNKNOWN state blocks fresh dispatch until explicit reconciliation

## Scope

Adds focused regression coverage for the local SQLite command idempotency and recovery ledger.

## Verification scenario

- UNKNOWN state blocks fresh dispatch until explicit reconciliation.
- Confirms failed or duplicate operations do not silently alter persisted state.

## Safety boundary

This test does not authenticate external evidence, prove exactly-once physical execution, guarantee power-loss durability across all filesystems, or certify TrainOS for safety-critical deployment.
