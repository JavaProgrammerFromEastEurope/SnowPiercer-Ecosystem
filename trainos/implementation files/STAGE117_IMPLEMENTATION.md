# Stage 117 — lease-renewal process crash boundaries

## Scope

Added subprocess crash-injection tests for the durable SQLite COMMIT boundary in
`EventLogRecoveryAttemptStore.renew_lease()`. The child process exits abruptly
with `os._exit()` immediately before COMMIT or immediately after the real COMMIT
returns. A fresh process then reads the journal and performs the valid terminal
transition from the durable state.

## Acceptance criteria

- A crash before COMMIT leaves the previous lease expiry durable.
- A crash after COMMIT preserves the renewed expiry despite losing the API return.
- Both cases preserve `IN_PROGRESS`, owner UUID, and fencing token until a valid
  terminal transition is performed.
- After restart, `finish_success()` transitions the row once to `SUCCEEDED`, clears
  ownership/lease, and a repeated terminal transition is rejected.
- No production code changed in this stage; the tests exercise the existing store.

## Validation results

- Stage 114–117 focused tests: **10 passed**.
- Full test suite: **729 passed**.
- `python -m compileall -q kernel tests`: passed.
- AST audit of all Python files under `kernel/` and `tests/`: passed: **2,595 Python files, 0 parse errors**.

These tests use a local SQLite file and subprocess crash injection; they are not a
claim of hardware-in-loop validation or production safety certification.
