# Stage 493 — Keep invalid-history validation read-only

## Implementation

Sequence-gap diagnostics must not repair, normalize, or otherwise mutate the backup being inspected.

## Test coverage

The SHA-256 of a malformed backup is identical before and after validation.

## Safety boundary

This stage validates local SQLite backup consistency. It does not prove off-host durability, distributed exactly-once execution, or external payment-provider safety.
