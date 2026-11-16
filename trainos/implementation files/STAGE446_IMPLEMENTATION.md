# Stage 446 — Preserve restored reconciliation audit after reopen

## Scope

Creates and backs up a reconciled command, opens the backup as a store, and confirms the completed state and audit validation survive reopening.

## Contract

Restored ledger state and reconciliation evidence remain consistent after a new connection opens the backup.

## Verification

Automated test: `tests/stage446/`. The release manifest records the aggregate targeted and regression test results.
