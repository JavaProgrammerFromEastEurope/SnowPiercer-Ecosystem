# Stage 162 — Duplicate execution-binding recovery guard

## Scope

This stage hardens cross-journal inspection against a damaged or restored idempotency database where the unique execution-binding index is absent and multiple idempotency records refer to one execution ID.

## Changes

- Added `CommandIdempotencyStore.count_execution_bindings()` as a read-only integrity query.
- Updated `ExecutionJournalConsistencyChecker.inspect()` to report `CONFLICT` and deny dispatch when an execution ID is bound to zero/multiple idempotency records at the point where a record is being inspected. The zero case is defensive; ordinary inspection starts from an existing record and should count at least one.
- Added regression coverage for corrupted duplicate bindings and for normal API rejection of a duplicate binding.
- A separate record with a unique binding remains inspectable; the checker does not globally block unrelated commands.

## Safety boundary

The normal SQLite unique index remains the primary write-time guard. The added check is a diagnostic fail-closed guard, not a distributed transaction or safety certification. It does not prove exactly-once execution at an external device.
