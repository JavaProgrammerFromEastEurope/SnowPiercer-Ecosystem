# Stage 132 — Fail-closed handling of invalid recovery journal states

## Scope

- Convert an unknown or malformed persisted status into `RecoveryAttemptBlocked` with an explicit manual-reconciliation message.
- Test a corrupted status during both read and begin-attempt paths.
- Verify the failed operation does not overwrite the corrupt row or leave a SQLite transaction open.
- Verify a valid terminal `succeeded` state cannot be restarted using the same attempt key.

## Implementation

The row decoder now validates the persisted status and raises a domain-specific blocked exception when the value is not a member of `RecoveryAttemptStatus`. It does not guess a replacement state or automatically repair the journal.

## Safety boundary

This is fail-closed behavior for a local SQLite journal. It does not make the database tamper-proof or establish readiness/certification for real train hardware. Manual reconciliation remains an operational requirement after journal corruption.
