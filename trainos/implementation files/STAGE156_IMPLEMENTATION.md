# Stage 156 — process-level idempotency claim races

Added multiprocessing regression tests for concurrent calls to `CommandIdempotencyStore.claim` using independent SQLite connections and a synchronized start barrier.

Scenarios:
- Identical key, command, payload, and execution binding: exactly one process creates the claim; the other observes the existing record.
- Same key with different commands: one claim wins and the other receives `IdempotencyConflict`; the stored row remains the winner's record.
- Different keys with the same `execution_id`: the unique database constraint allows only one binding and the other process receives a conflict.

The production implementation was not changed: SQLite `BEGIN IMMEDIATE`, the primary key, and the partial unique execution-id index enforce the tested invariants.

These tests exercise the local SQLite store only; they do not establish exactly-once behavior in an external executor or certify TrainOS for real train control.
