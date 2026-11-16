# TrainOS Stage 113 — Cross-Process Attempt Creation and Crash Windows

## Goal

Exercise recovery-attempt ownership using real child processes: abrupt process exit after durable creation and competing processes attempting to consume a single authorized retry.

## Changes

- Added `tests/stage113/test_recovery_attempt_process_races.py`; no production code changed because the existing `BEGIN IMMEDIATE`, owner PID, owner UUID, fencing token, and explicit retry authorization contract already handled the tested cases.
- A spawned process creates an attempt and exits via `os._exit(0)` without closing the store. A new process observes the dead owner, transitions the journal to `FAILED`, and cannot proceed until explicit authorization. The authorized successor increments the attempt count and fencing token exactly once and receives a new owner UUID.
- Two spawned processes are sequenced around an authorized retry. The first obtains ownership; the second is rejected while the owner is live. The durable attempt count and fencing token remain unchanged, and the first owner can finish.

## Validation

Run the focused Stage 113 tests, the complete pytest suite, `compileall`, AST parse audit, and ZIP integrity check. Exact results are recorded in the stage completion response after execution.

## Limitations

These are OS-process and SQLite integration tests, not physical power-loss tests, distributed-host fencing, storage-controller tests, or hardware-in-loop validation. PID liveness remains a same-host best-effort guard; TrainOS is not thereby production-safe or certified for real train control.
