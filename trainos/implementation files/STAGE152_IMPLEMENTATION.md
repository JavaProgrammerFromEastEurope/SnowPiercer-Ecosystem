# TrainOS Stage 152 — durable command idempotency ledger

Adds `CommandIdempotencyStore`, a SQLite-backed ledger for callers that cross an external execution boundary.

- A first claim persists an idempotency key and canonical SHA-256 fingerprint of the command name and payload.
- Repeating the same key and semantically equivalent JSON payload returns the existing record without authorizing a second execution.
- Reusing a key for a different command or payload raises `IdempotencyConflict`.
- Completion is idempotent only when the stored result matches; conflicting duplicate results are rejected.
- An uncertain external outcome can be marked `unknown`. Normal completion is then blocked until explicit reconciliation with non-empty evidence.
- Reconciliation is recorded durably in a separate audit table in the same transaction as the completion transition.
- SQLite `BEGIN IMMEDIATE` serializes competing claims; tests cover two independent connections.

This is an application-level durable ledger, not an exactly-once guarantee across arbitrary external systems. The external receiver must honor the same idempotency key, or provide an independently queryable state for reconciliation. It is not safety-certified for train control.
