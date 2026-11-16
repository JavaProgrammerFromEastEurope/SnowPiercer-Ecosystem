# TrainOS v103 — safety argument and limitations

## Established in the current Linux/Python test environment

1. Both input ZIPs pass CRC verification and all of their self-described manifest hashes match their source members.
2. v102 removed only interpreter/testing caches, not source; the 24-domain registry is unchanged.
3. Focused v103 tests verify exit codes, bounded timeout, direct SIGKILL of a test leader, SIGTERM of a main-thread Runner and best-effort cleanup of original process-group descendants.
4. The isolated SIGKILL-of-Runner probe **confirms a safety deficiency**: the per-file child remains running until an independent external authority kills and reaps it. This is a counterexample to any claim of comprehensive automatic cleanup.
5. Historical v101 evidence reports 1,487 passed strict full-suite tests and 24/24 per-file areas with a Linux subreaper. It is treated as archived evidence, not a substitute for a new v103 test.

## Limitations, BLOCKED / NO-GO

- Runner SIGKILL cleanup is **not** guaranteed by the Python Runner alone. The available subreaper handles orphan reaping, not an OS-enforced supervision boundary preventing detached descendants from surviving arbitrary failures.
- A SIGKILL between `Popen` and process registration/handler installation can bypass Python cleanup. Neither `start_new_session` nor `killpg` substitutes for production cgroup containment.
- An independently re-sessioned grandchild can escape the original subprocess group; a different UID may make signal delivery impossible. No cross-UID production verification, privilege-separated admission, SQLite crash-point or physical TrainOS integration claim is made.
- `TRAINOS_KERNEL_WORKERS` is an opt-in CI performance path, not equivalent to the original strictly serial fail-fast order. Tests sharing mutable global state can race.
- Container PID 1 semantics are environment-dependent. `PR_SET_CHILD_SUBREAPER` is a local test technique, not proof that actual deployment's init/supervisor configuration works.
- Test results demonstrate the tested software scenarios only. SnowPiercer system readiness cannot be inferred from the number of versions, source files or green tests.

## Conditions for lifting the gate

Independent end-to-end proof must cover production PID1 or cgroup cleanup across runner SIGKILL, orphaned/detached descendants, signal/timeout races, required security and privilege boundaries, and full release-specific regressions under the intended deployed execution mode. Until that evidence exists: **BLOCKED / NO-GO**.
