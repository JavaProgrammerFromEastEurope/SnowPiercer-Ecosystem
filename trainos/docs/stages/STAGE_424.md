# Stage 424 — SQLite ledger concurrency and backup safety

## Contract

Backup destinations must be file-backed and cannot be the special in-memory database.

## Verification

Automated test: `tests/stage424/test_stage424_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
