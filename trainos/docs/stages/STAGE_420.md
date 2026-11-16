# Stage 420 — SQLite ledger concurrency and backup safety

## Contract

The store backup API creates a consistent, integrity-checked, reopenable snapshot.

## Verification

Automated test: `tests/stage420/test_stage420_schema_recovery.py`.

## Boundary

This stage verifies local SQLite behavior only. It does not prove distributed exactly-once execution, arbitrary media failure recovery, disaster-recovery RPO/RTO, or external payment safety.
