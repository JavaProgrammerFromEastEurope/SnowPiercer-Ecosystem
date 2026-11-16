# Stage 386 — Ledger integrity diagnostics

## Objective
Validate a specific integrity-diagnostic contract for the durable command ledger.

## Test coverage
store.close()

## Safety boundary
Diagnostics are read-only and report findings; they do not repair records automatically. Passing these local tests is not evidence of distributed exactly-once execution or external payment safety.
