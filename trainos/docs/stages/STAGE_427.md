# Stage 427 — SQLite ledger concurrency and backup safety

## Contract

The final backup acceptance check verifies SQLite integrity, schema version, and the expected record.

## Verification

Automated test: `tests/stage427/test_stage427_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
