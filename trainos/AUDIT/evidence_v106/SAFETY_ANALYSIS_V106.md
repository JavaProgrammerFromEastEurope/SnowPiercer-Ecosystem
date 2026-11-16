# TrainOS v106 safety case and counterexamples

## Claim status

**BLOCKED/NO-GO**. Software correctness evidence does not establish OS-managed containment or safe operation of rolling stock, power systems, life support, freight or production payments. Existing TrainOS Python interfaces remain development-compatible; production legacy API and IPC cannot be fenced by an environment variable.

| Hazard / failure mode | Prevention / detection | v106 evidence | Safety conclusion |
|---|---|---|---|
| Runner SIGKILL while detached child executes | v105 external subreaper, pidfd identity | v105 historical PASS; strict v106 tests include v105 test | Covered for tested development environment only |
| Supervisor SIGKILL while Runner and double-fork grandchild run | Independent root authority and kernel cgroup.kill after supervisor exit | `DOUBLEFORK_SUPERVISOR_SIGKILL_V106.json` observed both processes still running, then independent *probe* cleanup | **Counterexample persists. Real cgroup authority path untested; NO-GO** |
| Authority SIGKILL | Independently managed system service, restart and cgroup sweep | No OS manager deployment; PID1 `supervisord` | **NO-GO; not demonstrated** |
| Faked cgroup control in temp directory | `statfs` cgroup2 magic and `/sys/fs/cgroup` ancestry, protected delegated root | `test_cgroup_authority_v106.py` unit-only; `CGROUP_HOST_PROBE_V106.json` | Denial shown, positive containment untested |
| Pre-exec escape / detached children | Pipe-blocked fork and `cgroup.procs` membership verification before exec; cgroup.kill on parent-exit | Code-level checks, synthetic `cgroup.kill` unit tests | **NOT** end-to-end certified |
| PID reuse / stale PID and PGID | pidfd for direct child and tracked v105 processes; cgroup membership for descendant fanout | v105 identity tests and strict v106 regressions | pidfd covered where used; prior PGID fallbacks still dev-only |
| Cross-UID and authenticated admission | Distinct authority/service/client UIDs; privileged OS broker and peer credentials still missing | `CROSS_UID_LEGACY_PROBE_V106.json` two real UIDs | Production denied; legacy development API callable; **NO-GO** |
| Concurrent startup attempts | root-only delegated cgroup and gate before exec | `ADMISSION_RACE_NEGATIVE_V106.json`: 16 simultaneous denied attempts | Negative control only, no successful concurrency path |
| Forged admission or legacy bypass | root-only service installation, immutable binary, OS-managed IPC ACLs | Direct legacy Runner remains invocable with env unset | **Known bypass / NO-GO** |
| Premature success with live descendants | supervisor checks process table; authority polls `populated` and always writes `cgroup.kill` | tests + code, but no real writable delegated cgroup | **NO-GO** |
| Timeout and SIGTERM | development supervisor returns 124/143 and reaps observed children | `PROCESS_BOUNDARY_PROBES_V106.json` | PASS for probes; not production containment |
| `ResourceWarning` / `DeprecationWarning` silently ignored | strict error flags and negative-control pytest | `WARNING_NEGATIVE_CONTROL_V106.json`, exit 1 with 2 expected failures | Policy effective in probed execution |
| Incomplete historical data / version regression | compare every v105 file with manifest; archive CRC, SHA-256 | `PARENT_V105_INTEGRITY.json`, build report | Verified source lineage; not behavioral equivalence |
| Test environment mode bits lost on extraction | read UNIX mode metadata from v105 ZIP and restore mode bits | `strict_full_1` FAIL retained; `ZIP_MODE_RESTORATION_V106.json` | Corrected local environment; rerun mandatory |

## Assumptions and non-assumptions

`PR_SET_CHILD_SUBREAPER` can adopt/reap surviving orphaned grandchildren **only while the supervisor is alive**. A Linux pidfd uniquely identifies one process while open; it does not identify a detached descendant the supervisor failed to observe. A cgroup is the appropriate kernel fanout container, but this host does not grant a writable cgroup-v2 subtree. A synthetic tempfile cannot prove that the Linux kernel enforces containment. Directory ownership and distinct numeric UID arguments cannot establish IPC client authentication, legacy production fencing or host supervisor restart.

**Certification gates:** independent delegated cgroup actual creation, real `cgroup.procs` attach-before-exec, genuine kernel `cgroup.kill` after supervisor SIGKILL (with setsid/double-fork), watcher restarted after authority SIGKILL, cross-UID/IPC credentials, OS DAC/ACL fences on legacy state and binaries, crash-point and race matrix, all test modes and full strict regressions. Until all gates have independent evidence, status stays BLOCKED/NO-GO.
