# TrainOS v105 — safety case and evidence boundaries

**Release decision: BLOCKED / NO-GO**, regardless of local PASS counts.

## Claims with local evidence
- `FinancialLedger` WAL admission: SQLite BUSY/LOCKED receives bounded retries; other failures propagate. A `BaseException` during constructor closes the database handle. See strict `test_financial_ledger_v105.py` and full-regression logs.
- Two worker CI test races were strengthened: SIGTERM-resistant descendants signal readiness *before* bounded timeout; `/proc` child termination uses bounded observation with a hard FAIL if still running. No expected SIGKILL or non-running assertion was removed.
- External Linux supervisor v105 signals previously observed descendants via `pidfd_open` / `pidfd_send_signal` after checking `/proc` start_ticks; stale observations are rejected. pidfd is necessary but not sufficient for process-tree containment.
- Direct Runner in explicit `TRAINOS_KERNEL_PRODUCTION=1` and supervisor with `--production` reject startup before admitting commands. This policy does not restrict an operator or same-UID caller from unsetting the environment; **it is not OS-enforced legacy fencing**.
- Actual SIGKILL of Runner under supervisor v105 is tested with a detached descendant, independent cleanup and supervisor report.

## Demonstrated counterexample
- `SUPERVISOR_SELF_SIGKILL_NEGATIVE_CONTROL.json` records real SIGKILL of the supervisor while a Runner and a `setsid()` child remained running. Separate subreaper subsequently cleaned and reaped them. This is a concrete lack of containment by the supervisor alone.
- `CGROUP_PID1_PIDFD_PROBE_V105.json` records current PID1 (`supervisord`) and `EROFS` when attempting to create a delegated cgroup v2. No independent service manager / cgroup watchdog was configured or tested.

## Residual risks requiring future release
1. Kernel cgroup v2 delegation, per-job cgroup assignment before execution, independent OS service supervisor, PID namespace/PID1 lifecycle, audit and fail-closed process kill after SIGKILL of v105 supervisor.
2. Remaining `killpg(PGID)` numeric identity/race risk. PIDFD signals protect observed processes, but session/group operations are not pidfd-addressed.
3. Separate-UID adversarial processes, inherited FD spoofing, env manipulation, legacy direct Runner bypass and cgroup escape all remain unverified.
4. Application-level TrainOS safety, financial real-world controls and integration with physical SnowPiercer subsystems are outside this software-only regression scope.
5. The host's OS service manager could kill the verifier itself; harness-level timeout and `SIGKILL` cannot prove containment without an external authority.

Read `VERIFICATION_SUMMARY_V105.json` and individual attempts with `.json`, `.stdout.log`, `.stderr.log`, `.exitcode`. All failures are retained; repeated PASS never overwrites failures.
