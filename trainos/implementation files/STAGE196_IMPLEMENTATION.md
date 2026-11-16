# Stage 196 — Completed commands cannot acquire a fresh dispatch reservation

## Scope

Adds focused regression coverage for the local SQLite command idempotency and recovery ledger.

## Verification scenario

- Completed commands cannot acquire a fresh dispatch reservation.
- Confirms failed or duplicate operations do not silently alter persisted state.

## Safety boundary

This test does not authenticate external evidence, prove exactly-once physical execution, guarantee power-loss durability across all filesystems, or certify TrainOS for safety-critical deployment.
