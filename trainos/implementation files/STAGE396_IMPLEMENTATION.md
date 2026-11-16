# Stage 396 — Empty audit evidence is diagnosed

## Objective
Verify blank persisted evidence is reported without automatic repair.

## Verification
See `tests/stage396/test_stage396_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
