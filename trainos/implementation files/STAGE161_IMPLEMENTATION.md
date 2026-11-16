# Stage 161 — Cross-journal reconciliation after restart

This stage adds regression coverage for the boundary between the durable command idempotency ledger and the execution audit journal after reopening both SQLite databases.

Scenarios covered:

- A `RUNNING` execution is converted to `RECOVERY_REQUIRED` after restart. The idempotency claim remains unchanged, the consistency checker refuses dispatch, and no second execution is created.
- A terminal execution with an idempotency record still marked `CLAIMED` is reported as requiring reconciliation rather than replay.
- An idempotency record marked `UNKNOWN` remains blocked even when the audit journal reports completion; explicit reconciliation is still required.

The stage adds tests and documentation only; the existing recovery and consistency logic already enforces these fail-closed outcomes. Tests use local SQLite databases and do not establish guarantees for arbitrary external executors or real hardware.
