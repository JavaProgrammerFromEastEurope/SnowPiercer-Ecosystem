# Stage 497 — Verify restore and reopen preserve audit generations

## Implementation

A copied backup reopens with its current ledger state and ordered reconciliation generations intact.

## Test coverage

A restored database retains both not-executed events and dispatch generation 2 and validates again after reopen.

## Safety boundary

This stage validates local SQLite backup consistency. It does not prove off-host durability, distributed exactly-once execution, or external payment-provider safety.
