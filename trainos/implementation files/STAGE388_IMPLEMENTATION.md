# Stage 388 — Legacy schema migration preserves command records

## Objective
Create a pre-generation ledger schema and verify initialization migrates columns/indexes without losing existing rows.

## Verification
See `tests/stage388/test_stage388_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
