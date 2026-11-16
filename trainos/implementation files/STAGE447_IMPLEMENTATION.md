# Stage 447 — Keep UNKNOWN non-retryable after restore

## Scope

Backs up an uncertain dispatched command, reopens the backup, and repeats the claim. The existing UNKNOWN record is returned without authorizing another execution.

## Contract

Recovery preserves uncertainty and does not silently retry a potentially executed operation.

## Verification

Automated test: `tests/stage447/`. The release manifest records the aggregate targeted and regression test results.
