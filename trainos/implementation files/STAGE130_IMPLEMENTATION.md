# Stage 130 — Repeated ambiguous-commit recovery

## Scope

Added a regression test for repeated durable SQLite transitions whose COMMIT acknowledgement is lost while a fresh-connection verification is temporarily unavailable. The test restarts the store after each uncertain transition and verifies the recovered row rather than assuming the operation failed.

## Assertions

- A durable failure remains `FAILED` with its error and unchanged attempt count/fencing token.
- A durable retry authorization retains operator, reason, and checkpoint fingerprint across restart.
- Consuming that authorization increments attempt count and fencing token exactly once and clears one-shot authorization metadata.
- A second failure/restart preserves monotonic attempt and fencing values.
- The configured maximum of three attempts cannot be exceeded by either retry authorization or direct attempt creation.
- No production code change was needed for this regression scenario.

## Validation

Results are recorded from the Stage 130 execution environment. This is software-level SQLite fault-injection coverage only; it is not evidence of safety certification or readiness for real train control.
