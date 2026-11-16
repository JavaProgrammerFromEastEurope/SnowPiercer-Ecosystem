# Stage 371 — Crash Recovery and Ledger Consistency

## Objective
Evidence from an earlier dispatch generation cannot be reused for a later attempt.

## Test
`tests/stage371/test_stage371_crash_recovery.py`

## Limits
This validates local SQLite persistence and API contracts only. It does not establish distributed exactly-once execution, external-provider truth, production payment readiness, or PCI compliance.
