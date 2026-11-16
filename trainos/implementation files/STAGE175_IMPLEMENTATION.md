# Stage 175 — dispatch-generation migration and concurrency

## Scope

This stage adds regression coverage for upgrading older SQLite idempotency ledgers to the `dispatch_generation` schema while preserving durable dispatch reservations and reconciliation history.

## Scenarios covered

- A legacy command with `dispatch_started = 1` and no `dispatch_generation` migrates to generation 1.
- Existing reconciliation rows survive migration; legacy evidence remains generation 0 and cannot be reused after a later dispatch attempt.
- A fresh evidence record is stored against the current generation and a subsequent reservation increments the generation.
- Four independent processes opening the same legacy database concurrently all observe the same migrated record, with no lost generation or duplicate migration failure.

## Validation

The stage tests cover schema migration and process-level concurrent initialization. Passing tests do not prove SQLite storage survives every filesystem or power failure, and do not establish atomicity between a database reservation and an external physical action.
