# Stage 171 — Dispatch reservation crash recovery

## Goal

Make the durable `dispatch_started` marker affect journal consistency decisions
when a process restarts before an outcome has been durably recorded.

## Change

`ExecutionJournalConsistencyChecker` now returns
`RECONCILIATION_REQUIRED` for a `CLAIMED` idempotency record whose dispatch
reservation is already set. A reservation may have been committed immediately
before a crash, so the application cannot infer whether the external callback
was entered. The existing reservation remains durable and is never automatically
cleared or replayed.

## Regression coverage

- Simulates process death after reservation but before callback entry.
- Reopens both stores and verifies inspection and dispatch both fail closed.
- Verifies a blocked reservation does not prevent an independent command from
  dispatching.
- Verifies an explicit `UNKNOWN` outcome remains in reconciliation state.

## Safety boundary

This does not make SQLite and an external side effect atomic. A real executor
must provide its own idempotency/fencing contract, and unresolved outcomes need
an explicit, evidence-based reconciliation process. This stage is not a safety
certification for real railway hardware.
