# Stage 131 — Ambiguous commit row-mismatch regression tests

## Scope

Added regression tests for the recovery-attempt journal's ambiguous-COMMIT resolver. Each test simulates a COMMIT that succeeds, then an independent SQLite connection changes one durable field before the original connection reports a lost acknowledgement.

Covered mismatches:

- A finish-failure transition whose durable `status` is unexpectedly changed to `succeeded`.
- A retry-start transition whose durable `fencing_token` is unexpectedly changed.
- A retry-authorization transition whose `checkpoint_fingerprint` is unexpectedly changed.

## Expected behavior

The resolver must only treat a reported commit error as success when the complete durable row matches the pre-commit expected snapshot. For every mismatch, the original SQLite error is re-raised rather than silently resolving the transition as successful. Tests reopen the database and inspect the actual durable state.

## Production changes

None. The existing full-row comparison already rejects these mismatches; this stage locks that behavior in with regression coverage.

## Safety boundary

These tests exercise local SQLite journal behavior only. They do not establish tamper resistance, distributed ownership guarantees, or readiness/certification for real train hardware.
