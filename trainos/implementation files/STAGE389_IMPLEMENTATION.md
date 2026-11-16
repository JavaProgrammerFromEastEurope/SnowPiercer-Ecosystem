# Stage 389 — Legacy dispatch reservation backfill

## Objective
Verify a legacy durable dispatch reservation is backfilled to a nonzero generation.

## Verification
See `tests/stage389/test_stage389_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
