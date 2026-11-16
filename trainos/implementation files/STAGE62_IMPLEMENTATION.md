# TrainOS Stage 62 — Durable diagnostic investigation records

## Implemented

- Added `DiagnosticInvestigationStore`, a SQLite-backed versioned store for JSON-compatible investigation snapshots and artifacts.
- Records are identified by `(record_type, record_id)` and saved as immutable revisions. `expected_revision` provides optimistic concurrency control; `0` creates a record and a positive value must match the latest revision.
- Each revision is SHA-256 checksummed and linked to the previous revision. Saves run in an atomic SQLite transaction.
- `load`, `history`, and `verify_integrity` validate the revision chain before returning data; corruption is reported, never silently repaired.
- Added typed results and exceptions: `StoredInvestigationRecord`, `InvestigationRecordVersion`, `InvestigationStoreIntegrityIssue`, `InvestigationStoreIntegrityError`, and `InvestigationRevisionConflict`.
- Added tests for append/update/history, close-and-reopen persistence, stale revision conflicts, record isolation, invalid payloads, checksum tampering, missing revisions, closed-store behavior, and Unicode/nested JSON.

## Safety and limitations

- This is a durable storage primitive, not automatic persistence for the in-memory hypothesis registry or task tracker. Callers must explicitly serialize and save their snapshots.
- Hash chains detect changes to stored records but do not replace filesystem permissions, encryption, backups, independent audit storage, or key-based signatures.
- The store does not decide whether a hypothesis is correct, whether a fault is repaired, or whether equipment is safe to operate.

## Verification

- Focused Stage 62 tests: **9 passed**.
- Full test suite: **519 passed in 12.95s** (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; this avoids a test-process shutdown hang from auto-loaded environment plugins).
- `python3 -m compileall -q -x '(/\\.venv/|/\\.history/|/__pycache__/|/node_modules/)' kernel tests`: passed.
- AST parse of all kernel Python files: **2,124 files, 0 syntax errors**.
- ZIP integrity: checked after archive creation.
