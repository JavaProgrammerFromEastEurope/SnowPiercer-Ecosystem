# Stage 170 — Durable dispatch reservation

## Scope

Stage 169 held Python locks around inspection and callback entry, which coordinated
only callers sharing the same store objects. This stage adds a SQLite-backed,
compare-and-set reservation so independent store instances/processes using the
same idempotency database cannot all pass the dispatch boundary for one key.

## Changes

- Added a durable `dispatch_started` column with a migration for existing databases.
- Added `CommandIdempotencyStore.reserve_dispatch()`, which uses `BEGIN IMMEDIATE`
  and reserves only a claimed command with an execution binding.
- Updated `dispatch_if_consistent()` to reserve before invoking the callback.
- A duplicate attempt fails closed with `RECONCILIATION_REQUIRED`.
- If the callback raises after entry, the reservation is retained and the record is
  marked `UNKNOWN` where possible; automatic replay remains blocked.
- Added tests for competing independent store instances, reservation persistence
  after reopening, and uncertain callback outcomes.

## Limitations

This coordinates attempts sharing one SQLite database. It does not make an
external side effect atomic with SQLite, does not fence devices that ignore
idempotency/fencing tokens, and cannot determine whether a callback that raised
performed its external action. Such outcomes require explicit reconciliation.
