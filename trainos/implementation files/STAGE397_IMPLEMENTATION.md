# Stage 397 — Corrupt ledger remains byte-for-byte logically unchanged by diagnostics

## Objective
Snapshot selected rows around diagnostics and ensure checks do not mutate data.

## Verification
See `tests/stage397/test_stage397_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
