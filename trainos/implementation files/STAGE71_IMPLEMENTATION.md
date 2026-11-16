# TrainOS Stage 71 — Recovery restart integration

## Scope

Stage 71 adds cross-stage integration tests for interrupted diagnostic evidence tasks. It does not change production behavior.

## Verified behavior

- A task moved from `in_progress` to `recovery_required` can be persisted to SQLite, survive closing and reopening the database, and restore through `restore_checkpoint_with_assessment()` with a consistent integrity report.
- The restore does not increment attempts or silently retry the task.
- A restored `recovery_required` task prevents the investigation report from declaring expert-review readiness.
- An explicit operator `block` decision after restart records the actor and decision note, moves the task to `blocked`, and decrements the recovery-required count.

## Verification

- Stage 71 focused tests: **3 passed**.
- Full test suite: **568 passed in 1.72 seconds**, pytest exited normally with exit code 0.
- `compileall` for `kernel` and `tests`: passed.
- AST parse of all **2,127** kernel Python files: **0 syntax errors**.
- ZIP integrity: checked after packaging.

The earlier Stage 70 report noted that a full pytest run had printed its passing summary but failed to exit within the external timeout. That behavior was not reproducible in Stage 71: both the ordinary full-suite run and the focused run exited normally. The test suite does not establish exactly-once behavior for external side effects or certify TrainOS for real-world train control.
