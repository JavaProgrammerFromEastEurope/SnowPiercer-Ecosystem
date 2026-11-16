# Stage 422 — SQLite ledger concurrency and backup safety

## Contract

Read-only integrity diagnostics detect an index with the expected name but incorrect uniqueness.

## Verification

Automated test: `tests/stage422/test_stage422_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
