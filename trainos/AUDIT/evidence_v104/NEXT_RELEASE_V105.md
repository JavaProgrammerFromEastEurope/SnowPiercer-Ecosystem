# TrainOS v105 — proposed next release (not implemented in v104)

## Primary blockers from v104 evidence

1. **SQLite financial ledger initialization contention.** Strict full test
   attempts #3 and #4 failed with `sqlite3.OperationalError: database is
   locked` while `PRAGMA journal_mode=WAL` ran in `FinancialLedger.__init__`
   under concurrent constructors. Design bounded retry/backoff or coordinated
   WAL initialization without altering public interfaces, verify rollback,
   resource closure, and at least 100 repeated concurrent starts. The failure
   remains BLOCKED until green under contention and end-to-end evidence.
2. **Eliminate process-identity TOCTOU.** Replace procfs-read-then-`kill(pid)`
   with identity-bound Linux pidfd signaling, include PID reuse stress and
   permissions failures; preserve existing signals/timeouts/exit contracts.
3. **Mandatory production containment.** Require an OS service manager with
   delegated writable cgroup v2, `cgroup.kill`, identity-bound admission,
   process-group and detached-child cleanup, independent of the Runner and
   test harness. Fail closed on service manager or supervisor SIGKILL.
4. **Worker-mode timing regression.** Four-worker attempt #1 failed
   `test_bounded_pytest_v94.py` and `test_kernel_runner_v102.py` under
   process contention. Diagnose actual cleanup with independent process
   evidence; correct race-prone assertions without suppressing warnings or
   weakening fail-closed checks; fix fixture ResourceWarning.
5. **Legacy production bypass.** Prevent direct unsupervised production
   execution while retaining existing library methods in development mode.
6. **Repeat all acceptance checks.** Three independent strict full PASS,
   three strict joint PASS, one complete serial per-file Kernel Runner PASS,
   worker/batch comparisons, SIGTERM/SIGKILL with descendants and real
   process races. Preserve all failed attempts, source hashes, evidence and
   cumulative ZIP. Do not infer physical SnowPiercer readiness.

**Readiness must remain BLOCKED / NO-GO** until these boundaries are verified.
