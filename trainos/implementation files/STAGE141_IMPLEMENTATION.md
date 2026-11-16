# Stage 141 — Retry authorization crash before COMMIT

## Scope

Adds a process-crash regression test for the boundary after `authorize_retry`
updates its row inside a SQLite transaction but before the transaction's COMMIT
is executed. This complements the existing Stage 122 test, which covers a crash
after the authorization COMMIT has already become durable.

## Expected behavior

- The uncommitted authorization update is rolled back when the process exits.
- The journal remains `FAILED`, with no authorization metadata and unchanged
  attempt count / fencing token.
- `begin_attempt` remains blocked until a fresh explicit authorization commits.
- A subsequently authorized attempt starts with the next attempt count and fencing
  token, and a new owner run ID.

## Implementation impact

Test and documentation only. No production-code changes were needed: SQLite's
transaction rollback preserved the prior committed row in this local test setup.
This is not a claim of power-loss certification, distributed consistency, or train
safety certification.
