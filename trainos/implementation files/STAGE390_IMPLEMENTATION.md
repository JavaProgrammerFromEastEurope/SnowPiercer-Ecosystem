# Stage 390 — Missing execution uniqueness index is diagnosed read-only

## Objective
Drop the execution-ID unique index and ensure diagnostics report the loss without silently recreating it.

## Verification
See `tests/stage390/test_stage390_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
