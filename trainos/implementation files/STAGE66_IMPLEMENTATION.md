# TrainOS Stage 66 — Interrupted-task outcome reconciliation

## Implemented

- Added `kernel/command/events/interrupted_task_reconciliation.py` with immutable observation, finding, assessment, and report records plus a read-only `InterruptedTaskReconciler`.
- Accepts caller-supplied observations for tasks in `recovery_required` and validates task identity, supported status, timezone-aware timestamp, observer, note, and evidence-ID shape.
- Produces conservative recommendations:
  - `confirmed_not_started`: retry may be considered only after authorized review and only while attempts remain.
  - `confirmed_completed`: independent verification is required; completion is never applied automatically.
  - `partial_or_unknown`: retain recovery-required state.
  - `external_effect_detected`: retain recovery-required state and reconcile side effects before retry.
  - missing/duplicate/invalid observations, unknown task IDs, and observations for non-recovery tasks are reported.
- Exported the new API from `kernel.command.events`.
- Added 9 tests in `tests/stage66/test_interrupted_task_reconciliation.py`.

## Safety and scope

This stage is decision support only. It does not query external systems, authenticate the observer, prove supplied evidence is authoritative, mutate task state, execute tasks, or guarantee exactly-once side effects. A `safe_to_retry_after_authorized_review` recommendation is not authorization to retry; the existing explicit `resolve_recovery_required()` gate remains required. The caller must independently establish that external state was checked.

## Verification

- Stage 66 focused tests: **9 passed**.
- Legacy stages 1–44 test selection: **370 passed**.
- Stages 46–66 test selection: **130 passed**.
- Full-suite run reached 100% progress with no failure output (547 collected tests), but the pytest process did not terminate before the execution timeout. Therefore this is **not recorded as a clean full-suite exit**.
- `compileall` and AST syntax checks are recorded in the accompanying build notes after execution.
