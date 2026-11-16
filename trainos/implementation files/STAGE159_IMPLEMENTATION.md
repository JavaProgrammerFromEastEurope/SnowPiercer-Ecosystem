# Stage 159 — concurrent completion and reconciliation

Added process-level tests for races in `CommandIdempotencyStore.reconcile_completed`.

- Two processes reconcile the same `UNKNOWN` key with conflicting results: one result wins durably and the other receives `IdempotencyConflict`.
- Two processes reconcile the same key with the same result: both observe the same completed result, while only the winning transition appends a durable reconciliation audit row.
- The tests use independent spawned processes and independent SQLite connections, with a barrier to synchronize contention.

No production code changes were required for these cases. This validates the local SQLite transaction boundary only; it does not establish exactly-once execution in an external system.
