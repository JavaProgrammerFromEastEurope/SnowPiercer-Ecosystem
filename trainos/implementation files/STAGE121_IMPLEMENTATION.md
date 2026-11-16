# Stage 121 — Cross-process ambiguous COMMIT races

## Scope

Added cross-process regression tests for two SQLite recovery-journal boundaries:

1. A finisher durably commits `SUCCEEDED`, pauses before returning from `commit()`, and then reports a simulated lost acknowledgement. A separate process observes the committed terminal row and attempts `finish_failure()`. The competing transition must be rejected, and the original process must resolve the ambiguous result from the exact durable row snapshot.
2. Two independent processes race to authorize retry for the same `FAILED` attempt. Exactly one authorization may commit; the other must be blocked after observing the state transition.

## Production changes

None. This stage exercises existing `BEGIN IMMEDIATE`, terminal-state validation, and full-row ambiguous-COMMIT resolution.

## Validation

Run the focused tests and complete test suite before marking this stage complete. These are local SQLite/process tests and do not establish distributed-database guarantees or train safety certification.
