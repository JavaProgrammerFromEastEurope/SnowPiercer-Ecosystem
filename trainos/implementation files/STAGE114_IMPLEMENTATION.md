# Stage 114 — Lease renewal and finish races

## Scope

This stage adds regression coverage for races between lease renewal and terminal
completion, stale owners attempting operations after a fencing-token increment, and
SQLite failures during lease renewal. Production logic was not changed because the
existing `BEGIN IMMEDIATE` transactions and conditional status/owner/token checks
passed these tests.

## Verification

- A two-process race exercises renewal and finish against the same attempt. The
  durable result must be exactly one terminal `SUCCEEDED` state, with the original
  fencing token and no active owner or lease. A renewal may succeed before finishing
  or be rejected after the terminal transition.
- A former owner cannot renew or finish after an explicitly authorized new attempt
  increments the fencing token.
- A SQLite trigger aborting the lease update leaves the attempt unchanged, rolls back
  the transaction, and leaves the connection usable for a subsequent valid renewal.

These are software-level concurrency and SQLite fault-injection tests. They do not
establish distributed-lock guarantees across hosts or certify physical train control.
