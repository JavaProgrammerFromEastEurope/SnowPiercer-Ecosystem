# TrainOS v107 — Failure / hazard analysis

**Safety decision: BLOCKED / NO-GO**. Analysis covers Linux process isolation,
not railway or life-support hardware certification.

| Hazard | Trigger | Required fail-closed mitigation | This environment |
|---|---|---|---|
| H-01 supervisor SIGKILL | abrupt death with setsid/double-fork descendants | independent managed cgroup, `cgroup.kill` | Negative counterexample reproduced: processes survive without OS containment |
| H-02 authority SIGKILL | loss of pre-exec gate owner or live cgroup | watchdog outside cgroup, unconditional sweep | Production denied; real positive recovery untested |
| H-03 watchdog SIGKILL | systemd restart delay | OS PID1 restarts service, startup sweep before admission | PID1 supervisord; fail-closed only; service restart NOT proven |
| H-04 escape / cgroup migration | writable group controls, capabilities, root namespaces | root ownership 0700, no delegated writer capabilities | Real migration attempts within managed cgroup untestable |
| H-05 PID reuse | asynchronous process identity changes | pidfd signal and start-time checks | v105/v106 tests; no exhaustive kernel fuzz |
| H-06 cross-UID spoof | JSON asserts fake UID | SO_PEERCRED allowlist; JSON mismatch denied | Real distinct-UID probes PASS |
| H-07 replay | repeats on same socket or restart | SQLite atomic uniqueness | Replays rejected, including after restart |
| H-08 journal swap / rollback | attacker modifies SQLite | protected directory + DB ownership/mode, transactional nonce tracking | OS ACLs exercised only in local probe; physical rollback not certified |
| H-09 direct legacy bypass | library invoked without production flag | OS-enforced privsep write service | **OPEN:** constructor callable as non-root UID |
| H-10 stdout/stderr/resource leaks | timeout, unraisable warning | strict pytest, process supervisor, captured evidence | Dedicated tests; only completed runs count |
| H-11 multiple manager race | concurrent watchdog startup | root-owned, O_NOFOLLOW file and kernel flock | Lock-exclusion test PASS; systemd multi-instance not E2E verified |
| H-12 untrusted cgroup path | symlink or altered group ownership | check root owner, mode, exact regex, refuse | Unit tests; mounted cgroupfs inaccessible for positive run |

## Evidence handling

- Keep every unsuccessful attempt and the real process exit status. In
  particular a pytest PASS with a failed report-writing harness is NOT a PASS
  evidence run.
- `cgroup.kill` mock tests are labeled synthetic; do not call them production.
- Any attempt to admit production on the present read-only host must return
  a denial before running requested commands.
- Do not weaken ResourceWarning or DeprecationWarning errors for throughput.

## Remaining system safety work

Deploy actual root-owned cgroup2 delegation in an independent systemd sandbox,
replace deny-only broker with state-bound permits and a trusted admission IPC,
block legacy store writes by OS UIDs and ACLs, prove authority/watchdog restart,
conduct real SIGKILL/rollback/replay/escape/crash-point matrix and independent
safety certification. Physical SnowPiercer subsystems remain outside GO scope.

## Additional v107 design gaps

- `uid_broker_v107` is a bounded verification server rather than a
  production-managed durable RPC service. It has no client quota / rate limit;
  world-connectable Unix socket permissions permit attempted denial-of-service,
  although `SO_PEERCRED` denies unlisted UIDs. A future broker requires
  resource budgets and per-UID request throttling.
- The watchdog service template is deliberately unconfigured and not installed.
  It is statically parseable but cannot establish its own systemd restart
  guarantee from this container.
- A SIGTERM of an active watchdog is not independently proven to complete
  cleanup before service exit. This is a release-blocking lifecycle scenario.
- Neither a mocked `cgroup.events` nor a root-owned ordinary temporary directory
  demonstrates resistance to cgroup migration under a real Linux kernel.
- Future positive admission must handle kernel PID identity and transaction
  generation across broker-authority crashes, not only replay of deny-only
  requests.
