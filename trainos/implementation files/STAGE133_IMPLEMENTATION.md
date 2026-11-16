# Stage 133 — Recovery journal invariant validation

## Changes

- Validate persisted `attempt_count`, `max_attempts`, and `fencing_token` when decoding a journal row. Invalid counters and mismatched positive fencing tokens fail closed with `RecoveryAttemptBlocked`.
- Validate active modern ownership metadata (run ID, PID, positive fencing token, parseable lease timestamp) before using an `IN_PROGRESS` row.
- Preserve the previous `owner_run_id` as forensic context when a dead/interrupted attempt is transitioned to `FAILED`; PID and lease are cleared as before. Invalid or missing PID metadata is left to the existing recovery reconciliation policy rather than being prematurely normalized during row decoding.
- Add corruption tests that bypass SQLite CHECK constraints and confirm reads/transitions block without silently rewriting the damaged row.

## Validation

Run focused and complete pytest suites, Python compile checks, AST parsing, and archive integrity verification. These tests validate local SQLite journal behavior only; they do not certify TrainOS for real-world train control.
