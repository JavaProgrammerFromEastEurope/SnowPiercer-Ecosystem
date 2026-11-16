# Stage 391 — Malformed fingerprint is diagnosed read-only

## Objective
Corrupt a fingerprint and ensure diagnostics report it without rewriting the record.

## Verification
See `tests/stage391/test_stage391_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
