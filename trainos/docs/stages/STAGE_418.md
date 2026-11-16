# Stage 418 — SQLite ledger concurrency and backup safety

## Contract

Concurrent initializers serialize through SQLite and leave one valid, versioned schema.

## Verification

Automated test: `tests/stage418/test_stage418_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
