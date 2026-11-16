# Stage 176 — Cross-process reconciliation and dispatch race

## Scope

This stage adds regression coverage for multiple independent processes that race to reconcile an unknown command outcome and reserve a fresh dispatch generation.

## Scenarios

- Several processes submit the same evidence while trying to reserve the next generation. The durable SQLite transaction and reservation gate must permit at most one fresh dispatch reservation.
- Several processes submit conflicting evidence. The reconciliation history must remain singular and internally consistent; only the winning evidence may be recorded.
- After the new generation is reserved, evidence tied to the previous generation must not be reusable.

## Safety boundary

These tests validate the local SQLite coordination protocol on the tested platform. They do not prove external executor idempotency, authenticity of evidence, power-loss durability on every filesystem, or safety certification for physical transport systems.
