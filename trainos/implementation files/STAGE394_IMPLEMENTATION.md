# Stage 394 — Invalid audit decision is diagnosed

## Objective
Verify an unsupported audit decision is reported, not normalized.

## Verification
See `tests/stage394/test_stage394_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
