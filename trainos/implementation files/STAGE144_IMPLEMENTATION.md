# TrainOS Stage 144 — Reject stale ownership metadata outside active attempts

## Change

The recovery journal reader now rejects any non-`IN_PROGRESS` record that still contains `owner_pid`, `owner_run_id`, or `lease_expires_at`. Normal state transitions clear these fields atomically, so their presence in `FAILED`, `RETRY_AUTHORIZED`, or `SUCCEEDED` is contradictory persisted state rather than a safe opportunity to overwrite metadata.

## Validation

Regression tests inject each ownership field into each of the three non-active statuses, then verify both read and attempted transition fail closed, the transaction is rolled back, and the durable corrupted row remains available for manual reconciliation.

This is a software regression check, not a safety certification for real train hardware.
