# Stage 370 — Crash Recovery and Ledger Consistency

## Objective
Explicit not-executed reconciliation survives restart and permits a new generation only after evidence.

## Test
`tests/stage370/test_stage370_crash_recovery.py`

## Limits
This validates local SQLite persistence and API contracts only. It does not establish distributed exactly-once execution, external-provider truth, production payment readiness, or PCI compliance.
