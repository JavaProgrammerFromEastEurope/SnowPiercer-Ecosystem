# Stage 488 — Reject missing audit sequence entries

## Implementation

The backup validator now requires the global reconciliation sequence to be contiguous. A deleted middle row is treated as incomplete audit history, not as a valid snapshot.

## Test coverage

A three-event audit is altered by deleting sequence 2; validation must report a sequence gap.

## Safety boundary

This stage validates local SQLite backup consistency. It does not prove off-host durability, distributed exactly-once execution, or external payment-provider safety.
