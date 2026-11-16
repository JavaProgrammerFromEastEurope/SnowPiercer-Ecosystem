# Stage 421 — SQLite ledger concurrency and backup safety

## Contract

A backup is an independent point-in-time snapshot and excludes later writes.

## Verification

Automated test: `tests/stage421/test_stage421_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
