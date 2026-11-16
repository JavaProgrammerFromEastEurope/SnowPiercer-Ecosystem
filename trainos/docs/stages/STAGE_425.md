# Stage 425 — SQLite ledger concurrency and backup safety

## Contract

Concurrent claims for the same idempotency key have exactly one creator.

## Verification

Automated test: `tests/stage425/test_stage425_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
