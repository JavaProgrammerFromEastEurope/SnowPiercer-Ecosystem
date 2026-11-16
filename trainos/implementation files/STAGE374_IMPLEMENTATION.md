# Stage 374 — Crash Recovery and Ledger Consistency

## Objective
Completed reconciliation state, evidence, decision and generation remain aligned after reopen.

## Test
`tests/stage374/test_stage374_crash_recovery.py`

## Limits
This validates local SQLite persistence and API contracts only. It does not establish distributed exactly-once execution, external-provider truth, production payment readiness, or PCI compliance.
