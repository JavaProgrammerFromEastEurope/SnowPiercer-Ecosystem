# Stage 489 — Require audit history to begin at sequence one

## Implementation

The validator rejects a snapshot whose earliest surviving audit event starts above sequence one, indicating that the beginning of the append-only history is missing.

## Test coverage

A two-event audit loses sequence 1; validation must report that sequence 1 was expected.

## Safety boundary

This stage validates local SQLite backup consistency. It does not prove off-host durability, distributed exactly-once execution, or external payment-provider safety.
