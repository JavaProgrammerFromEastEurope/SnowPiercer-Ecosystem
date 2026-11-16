# TrainOS Stage 59 — Evidence task lifecycle tracking

## Implemented

- Added `DiagnosticEvidenceTaskTracker`, an in-memory state tracker for the evidence-collection tasks produced by Stage 58.
- Added immutable `TrackedEvidenceTask`, `EvidenceTaskTransition`, and `EvidenceTaskTrackerSnapshot` records and exported them from `kernel.command.events`.
- Registers plans idempotently using stable `(hypothesis_id, task code)` identities; conflicting definitions and capacity overflow are rejected without partial registration.
- Supports explicit `pending -> in_progress -> completed` tracking, retryable failures returning to `pending`, exhausted/non-retryable failures becoming `blocked`, and explicit blocking.
- Tracks attempts, result notes, evidence event IDs, actor, timestamps, and ordered transition history. Duplicate/blank evidence references are rejected.
- All state changes are guarded by a lock. Snapshot results are immutable and deterministically ordered.

## Safety and limitations

- The tracker records task progress only. It does not retrieve evidence, call external services, modify hypothesis assessments, or execute train/equipment commands.
- Storage is in-memory and not a durable audit log. Process restart loses task and transition state.
- A task marked `completed` means an operator recorded a result; it does not prove evidence quality or establish root cause. Evidence validation must still run separately.

## Verification

- Baseline before changes: **488 passed**.
- Stage 59 focused tests: **6 passed**.
- Full test suite: **494 passed**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parsing of all **2,121** kernel Python files: **0 syntax errors**.
- ZIP integrity: checked after archive creation.
