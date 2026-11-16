# TrainOS Stage 65 — Interrupted-task recovery

## Implemented

- Added `recovery_required` as an explicit evidence-task state for work that was in progress when a process stopped.
- Added `mark_interrupted_tasks_for_recovery()` to quarantine all `in_progress` tasks without incrementing attempts or retrying work.
- Added `resolve_recovery_required()` requiring an explicit `retry` or `block` decision with actor and rationale; retries are rejected when the configured attempt limit is exhausted.
- Persisted and restored the new state through investigation checkpoints, including state-count validation and allowed transition-history checks.
- Kept the existing task state transitions unchanged for ordinary successful and failed task paths.

## Safety and limitations

- Marking tasks as `recovery_required` is bookkeeping only; it does not inspect external systems or prove whether a task's side effects occurred.
- An operator must reconcile external state before authorizing a retry. The tracker cannot provide exactly-once execution for external side effects.
- Checkpoint state remains scoped to hypotheses and diagnostic tasks; it does not restore hardware state or event history.

## Verification

- Focused Stage 65 tests: **6 passed**.
- Full test suite: **538 passed**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parse of all kernel Python files: passed (2125 files, 0 syntax errors).
- ZIP integrity: passed after archive creation.
