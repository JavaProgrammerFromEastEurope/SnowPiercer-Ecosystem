# TrainOS Stage 163 — Concurrent Multi-Command Recovery

## Scope

This stage adds regression coverage for restart recovery across multiple command executions, concurrent recovery callers, and isolation when one execution's audit history is malformed.

## Tests added

- `tests/stage163/test_concurrent_multi_command_recovery.py`
  - Six concurrent recovery callers process eight interrupted executions without duplicate recovery transitions.
  - A malformed audit state for one execution does not stop an unrelated valid running execution from being marked `recovery_required`.
  - Recovery leaves terminal histories unchanged and is idempotent on a second pass.

## Safety behavior

Recovery marks interrupted running executions as `recovery_required`; it does not automatically replay commands. Journal consistency checks remain fail-closed. These tests are software regression tests, not evidence of hardware safety certification or exactly-once external side effects.
