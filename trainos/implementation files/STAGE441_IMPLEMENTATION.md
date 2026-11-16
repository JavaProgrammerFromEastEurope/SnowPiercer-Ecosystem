# Stage 441 — Reject orphan reconciliation audit rows

## Scope

Injects an audit row that references a missing idempotency key. Backup publication must fail before the destination is published and remove its temporary file.

## Contract

A backup with orphan audit history is rejected before publication; failed publication leaves no final or temporary artifact.

## Verification

Automated test: `tests/stage441/`. The release manifest records the aggregate targeted and regression test results.
