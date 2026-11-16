# Stage 140 — Recovery journal process-crash atomicity

## Scope

Adds a process-level fault-injection test for the SQLite recovery-attempt journal. A spawned worker creates an attempt through `EventLogRecoveryAttemptStore`, then uses `os._exit` to terminate without normal Python cleanup. A second spawned worker begins a journal transition, writes an incomplete terminal-state update, and exits before committing.

## Assertions

- A committed `IN_PROGRESS` attempt remains durable after abrupt owner-process exit.
- SQLite rolls back the uncommitted partial update after the second process exits.
- The row remains internally consistent: status, owner UUID, PID, fencing token, and lease remain from the committed snapshot.
- The normal store path subsequently detects the dead owner and commits `FAILED`, requiring explicit retry authorization.
- No automatic retry starts as a side effect of crash reconciliation.

## Limits

This exercises process termination and SQLite transaction recovery on the local test filesystem. It does not emulate power-loss behavior on every filesystem/storage controller, distributed database failures, hardware interlocks, or train safety certification. No production code change was needed for the invariant tested here.
