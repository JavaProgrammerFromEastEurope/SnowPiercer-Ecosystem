# Stage 116 — Lease Renewal vs. Finish Race

## Scope

Validate the lease-renewal and terminal-finish race across independent SQLite connections/processes, and ensure ambiguous renewal acknowledgements do not report success when another valid transition supersedes the exact expected row.

## Changes

- Added a spawned-process race between `renew_lease()` and `finish_success()`.
- Asserted the durable terminal state is `SUCCEEDED`, with ownership and lease cleared and the fencing token unchanged.
- Added a deterministic lost-acknowledgement scenario: renewal commits, a second store finishes the attempt, and the renewal wrapper raises. The renewal API preserves the commit exception because the durable row no longer matches the exact expected snapshot.
- No production code changes were needed; this stage tests the existing transaction and exact-row resolution contract.

## Verification

See the stage completion response for the executed focused/full suite, compile, AST, and archive checks. These tests exercise software-level SQLite behavior only; they are not hardware or physical power-loss tests.
