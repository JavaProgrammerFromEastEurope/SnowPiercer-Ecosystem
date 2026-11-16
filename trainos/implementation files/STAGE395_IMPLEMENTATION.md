# Stage 395 — Future audit generation is diagnosed

## Objective
Verify an audit generation newer than the command record is reported.

## Verification
See `tests/stage395/test_stage395_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
