# Stage 89 — Durable recovery-attempt journal

## Changes

- Added `EventLogRecoveryAttemptStore`, a separate SQLite-backed journal for recovery attempts.
- Persisted states: `in_progress`, `failed`, `retry_authorized`, and `succeeded`.
- A repeated attempt with the same key is blocked after failure or success. An attempt left `in_progress` by a process interruption is converted to `failed` and blocked until an explicit retry authorization is recorded.
- Retry authorization records an operator identifier and reason; the next attempt increments the attempt counter.
- Integrated the optional journal with `EventLogStartupRecovery.run()`. Compatibility is preserved when no attempt store is supplied. When enabled, failed recovery is persisted and successful candidate publication is followed by a durable success transition. If that transition fails, the newly published candidate is removed and startup returns `BLOCKED`.
- Exported the new API from `kernel.command.events`.
- Added five tests for retry authorization, interrupted-process recovery, duplicate success prevention, startup success journaling, and durable blocking after failed restoration.

## Validation

- `PYTHONPATH=. pytest -q`: 651 passed.
- Focused tests for stages 87–89: 16 passed.
- `python -m compileall -q kernel tests`: passed.
- AST parse of kernel Python sources: results recorded in the delivery response.

## Limitations

The journal prevents accidental retry loops but is not tamper-proof. It must be stored and access-controlled independently for stronger threat models. This module is not automatically wired into every TrainOS process entry point; callers must pass the journal and a stable attempt key. It is not a safety-certified train-control component.
