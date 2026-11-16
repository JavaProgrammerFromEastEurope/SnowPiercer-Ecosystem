# Stage 158 — concurrent recovery after lost COMMIT acknowledgement

Adds process-level regression tests for a durable idempotency claim whose COMMIT acknowledgement is lost.

- Two independent processes re-claim the same key, payload, and execution ID after reopening the database; both must receive the existing `CLAIMED` record.
- A competing process using the same key for a different command must receive `IdempotencyConflict`; the durable original record must remain unchanged.
- The tests use independent SQLite connections in spawned processes and verify the persisted row count and identity after the race.

The fault injection models an API-level lost acknowledgement after SQLite's commit returned successfully. It is not a physical power-loss or storage-device test, and it does not prove exactly-once execution by an external executor.
