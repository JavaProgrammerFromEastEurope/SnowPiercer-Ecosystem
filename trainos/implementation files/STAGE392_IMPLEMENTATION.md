# Stage 392 — Malformed result JSON is diagnosed read-only

## Objective
Corrupt completed-result JSON and ensure integrity diagnostics report semantic corruption.

## Verification
See `tests/stage392/test_stage392_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
