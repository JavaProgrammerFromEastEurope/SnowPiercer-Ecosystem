# TrainOS Stage 88 — Startup Recovery Orchestration

## Changes

- Added `EventLogStartupRecovery` with explicit `TRUSTED`, `RECOVERY_REQUIRED`, `RECOVERY_READY`, and `BLOCKED` outcomes.
- Startup assesses the active log against the independent anchor before returning a trusted status.
- If the active database is absent or untrusted, an optional backup may be restored to a distinct recovery candidate path. The active database is never automatically replaced.
- Candidate paths colliding with the active database, backup, or anchor database are rejected before restoration.
- Rejected recovery candidates remain unpublished; existing destination files are preserved.
- Exported the API from `kernel.command.events`.

## Validation

- Focused tests for Stages 86–88: 15 passed.
- Full test suite: 646 passed.
- `python -m compileall -q kernel tests`: passed.
- AST audit: 2,139 Python files, 0 parse errors.

## Limitations

- This is application-level startup orchestration, not a supervisor or service manager that automatically runs before every TrainOS process.
- Promotion of a recovery candidate is intentionally an explicit deployment/operator action.
- The anchor database must be independently protected. No guarantee is made against a privileged attacker able to rewrite both databases.
- Not safety-certified for real train control.
