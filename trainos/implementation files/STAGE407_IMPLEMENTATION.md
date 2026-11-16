# Stage 407 — Unsupported Schema Rejected Before Ledger Creation

## Objective

Validate schema-version compatibility or SQLite backup/restore behavior for the local command ledger.

## Verification

Automated test: `tests/stage407/test_stage407_schema_recovery.py`.

## Safety boundary

SQLite backup checks validate local data preservation only. They do not establish disaster-recovery RPO/RTO, external payment safety, or distributed exactly-once execution.
