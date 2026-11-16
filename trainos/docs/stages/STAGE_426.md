# Stage 426 — SQLite ledger concurrency and backup safety

## Contract

A backup/restore cycle preserves UNKNOWN state and does not implicitly authorize a retry.

## Verification

Automated test: `tests/stage426/test_stage426_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
