# TrainOS Stage 94 — Recovery journal failure boundaries

## Scope

Hardened terminal state transitions in `EventLogRecoveryAttemptStore` and added regression tests for interrupted SQLite writes and Stage 89 schema migration.

## Implementation

- `_finish()` now uses an explicit `BEGIN IMMEDIATE` transaction.
- Terminal state update and commit are handled as one transaction; exceptions roll back if SQLite still has an active transaction.
- A transition that affects no `IN_PROGRESS` row raises `RecoveryAttemptBlocked` without changing an existing terminal state.
- Added tests that inject a SQLite trigger failure during success transition, verify rollback and subsequent connection usability, and validate in-place migration of a legacy Stage 89 journal.

## Validation

See the test and audit results recorded for this archive at build time. Tests cover software-level SQLite failure injection, not physical power-loss durability or every filesystem/storage failure mode.

## Limitations

- The journal remains a local SQLite database and is not tamper-proof.
- A database commit does not establish safety certification for any train control function.
- Recovery candidates are not automatically promoted to the active event database.
