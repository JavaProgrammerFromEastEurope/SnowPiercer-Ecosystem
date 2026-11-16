# TrainOS Stage 93 — Recovery journal concurrency

## Objective
Prevent concurrent recovery callers from invalidating an active attempt and serialize retry authorization across independent SQLite connections.

## Changes
- Added a durable `owner_pid` column to `recovery_attempts`, with an in-place migration for existing Stage 89–92 journals.
- New attempts and authorized retries record the owning process ID. Successful/failed completion clears ownership.
- A second caller in the same process now receives `RecoveryAttemptBlocked` when an attempt is already active; it no longer marks that live attempt as interrupted.
- An `IN_PROGRESS` record owned by a different process is treated as an interrupted attempt and must be explicitly authorized before retry.
- `authorize_retry()` now uses `BEGIN IMMEDIATE` around its read/validate/update transaction, serializing competing authorization attempts across SQLite connections/processes.
- Added concurrent tests for retry authorization, consuming a retry authorization, and competing completion transitions.

## Validation results
- Full test suite: **664 passed**.
- Focused recovery tests (Stages 89–93): **18 passed**.
- `python -m compileall -q kernel tests`: passed.
- AST parse audit: **2,572 Python files, 0 parse errors**.
- ZIP integrity checked after packaging.

## Limits
`owner_pid` is a pragmatic process ownership signal, not a cryptographic identity. Operating-system PID reuse is possible; a production deployment should use a stronger process-instance identity/lease and store the journal on a durable, access-controlled volume. This journal is not tamper-proof. These changes do not certify TrainOS for controlling real train hardware.
