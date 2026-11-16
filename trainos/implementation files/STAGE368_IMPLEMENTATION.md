# Stage 368 — Crash Recovery and Ledger Consistency

## Objective
A dispatch reservation survives database reopen and is not issued twice.

## Test
`tests/stage368/test_stage368_crash_recovery.py`

## Limits
This validates local SQLite persistence and API contracts only. It does not establish distributed exactly-once execution, external-provider truth, production payment readiness, or PCI compliance.
