# Stage 393 — Orphan reconciliation audit is diagnosed

## Objective
Add an audit row referencing a nonexistent key and verify a clear finding.

## Verification
See `tests/stage393/test_stage393_ledger_recovery.py`. This stage validates local SQLite migration/diagnostic behavior only.

## Safety boundary
Integrity checks are diagnostic and must not silently repair corrupted records. Passing local tests does not establish distributed exactly-once execution or external payment safety.
