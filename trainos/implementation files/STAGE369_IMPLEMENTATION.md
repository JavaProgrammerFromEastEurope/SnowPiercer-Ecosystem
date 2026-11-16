# Stage 369 — Crash Recovery and Ledger Consistency

## Objective
UNKNOWN remains durable after restart and continues to block dispatch.

## Test
`tests/stage369/test_stage369_crash_recovery.py`

## Limits
This validates local SQLite persistence and API contracts only. It does not establish distributed exactly-once execution, external-provider truth, production payment readiness, or PCI compliance.
