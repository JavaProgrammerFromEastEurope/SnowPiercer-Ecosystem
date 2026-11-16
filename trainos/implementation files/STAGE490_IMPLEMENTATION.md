# Stage 490 — Enforce per-key dispatch-generation monotonicity

## Implementation

For each idempotency key, reconciliation generations may stay the same or increase, but must not regress as audit sequence advances.

## Test coverage

Two valid generation events are corrupted to appear in descending order and must be rejected.

## Safety boundary

This stage validates local SQLite backup consistency. It does not prove off-host durability, distributed exactly-once execution, or external payment-provider safety.
