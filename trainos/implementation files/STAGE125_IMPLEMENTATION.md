# Stage 125 — Crash before COMMIT in retry transactions

## Scope

Added process-level crash-injection tests for two SQLite write boundaries in
`EventLogRecoveryAttemptStore`: retry authorization and creation of the initial
attempt. The tests exit the child process after the target SQL statement executes
but before the surrounding `BEGIN IMMEDIATE` transaction can commit.

## Expected invariants

- An interrupted `authorize_retry()` update is rolled back on process exit. The
  durable row remains `FAILED`; authorization fields remain empty and attempt
  count, configured limit, and fencing token do not change.
- A retry can subsequently be authorized explicitly and started once, consuming
  one attempt and advancing the fencing token.
- An interrupted initial `INSERT` leaves no partial attempt row. A fresh process
  can create the first attempt with count 1 and fencing token 1.

## Validation

Run the focused Stage 125 tests first, then the complete test suite, compileall,
AST parsing audit, and ZIP integrity verification. These are local SQLite/process
crash simulations; they do not emulate sudden power loss or storage-controller
failure and do not certify TrainOS for physical transport control.
