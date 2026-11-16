# Stage 375 — Crash Recovery and Ledger Consistency

## Objective
A mismatched execution identity after restart cannot mutate UNKNOWN state or create audit state.

## Test
`tests/stage375/test_stage375_crash_recovery.py`

## Limits
This validates local SQLite persistence and API contracts only. It does not establish distributed exactly-once execution, external-provider truth, production payment readiness, or PCI compliance.
