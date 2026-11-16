# Stage 423 — SQLite ledger concurrency and backup safety

## Contract

A non-SQLite backup artifact is rejected instead of being accepted as a valid ledger.

## Verification

Automated test: `tests/stage423/test_stage423_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
