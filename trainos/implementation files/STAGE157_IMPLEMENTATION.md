# TrainOS Stage 157 — idempotency claim crash recovery

Added regression tests for the two important SQLite claim commit windows:

- A commit failure before durability is observed: the transaction is rolled back, no claim row remains, and a later process can claim the key.
- The database commit succeeds but the acknowledgement is lost: the caller observes an exception, but after reopening the database the same request returns the existing claim rather than creating a second row.

The tests inject a one-shot fault at the connection commit boundary and reopen the store to verify durable state. This is fault simulation at the SQLite API boundary, not a physical power-loss or storage-controller certification test.

No production code changes were required for these cases.
