# Stage 122 — Crash boundaries for retry authorization and startup

## Scope

Added two subprocess crash-injection tests around durable SQLite state transitions:

1. The process exits immediately after `authorize_retry()` commits `RETRY_AUTHORIZED`. On restart, the durable authorization is observed and consumed exactly once; a second start is blocked while the new attempt is live.
2. The process exits immediately after `begin_attempt()` commits `IN_PROGRESS` but before the API can return the new owner identity. On restart, the durable attempt is found. The dead owner is reconciled to `FAILED`, another start is blocked pending explicit authorization, and only then may a fresh attempt start with an incremented fencing token.

## Production changes

When `begin_attempt()` reconciles an interrupted `IN_PROGRESS` row to `FAILED`, it now clears `lease_expires_at` as part of the same transaction. The previous owner UUID remains in the row as forensic history; `owner_pid` is cleared. This was found by the crash-after-start test, which showed that a failed attempt could retain a stale lease timestamp. No other production behavior was changed.

## Validation

The tests use a real child process and `os._exit()` immediately after the selected commit, avoiding Python cleanup handlers. They validate local SQLite process-crash behavior only; they do not prove filesystem/power-loss durability, distributed failover, or train safety certification.
