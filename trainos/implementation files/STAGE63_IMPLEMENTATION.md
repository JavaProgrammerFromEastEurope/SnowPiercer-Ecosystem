# TrainOS Stage 63 — Atomic diagnostic investigation checkpoints

## Implemented

- Added `DiagnosticInvestigationCheckpointService` to persist hypothesis-registry and evidence-task-tracker snapshots together as one versioned record in the existing SQLite `DiagnosticInvestigationStore`.
- Checkpoints restore into typed immutable snapshot dataclasses, including hypotheses, assessments, tracked tasks, nested task definitions, and task transitions.
- Uses the store's atomic append transaction, SHA-256 revision chain, and optimistic `expected_revision` guard.
- Validates cross-snapshot references and task state counters before commit, preventing malformed/inconsistent snapshots from being persisted.
- Validates payload schema and consistency again on load. Corrupt/unsupported snapshots raise `InvestigationStoreIntegrityError`; no automatic repair is attempted.
- Exported the service and checkpoint type through `kernel.command.events`.

## Scope and limitations

- This is a checkpoint adapter, not automatic persistence for every in-memory mutation. Callers must explicitly save snapshots after desired state changes.
- Loading returns typed snapshots; it does not mutate or hydrate existing registry/tracker instances. A future controlled restore API should validate domain invariants before doing so.
- Hypothesis and task snapshots are committed atomically together, but event history and hardware state are outside this checkpoint.
- Hash chains detect ordinary tampering but are not keyed signatures and do not replace access control, independent backups, or external audit.

## Verification

- Focused Stage 63 tests: **5 passed**.
- Full test suite: **524 passed in 14.51s** with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
- `python3 -m compileall -q -x '(/\\.venv/|/\\.history/|/__pycache__/|/node_modules/)' kernel tests`: passed.
- AST parse of all kernel Python files: **2,125 files, 0 syntax errors**.
- ZIP integrity: verified after archive creation.
