# Stage 495 — Validate global sequence across multiple idempotency keys

## Implementation

The sequence is global to the reconciliation table rather than restarting for each idempotency key.

## Test coverage

Five independently reconciled keys validate with one contiguous global sequence.

## Safety boundary

This stage validates local SQLite backup consistency. It does not prove off-host durability, distributed exactly-once execution, or external payment-provider safety.
