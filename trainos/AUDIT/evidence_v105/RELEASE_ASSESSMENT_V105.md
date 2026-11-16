# TrainOS v105 — cumulative release assessment

**Decision: BLOCKED / NO-GO.** The software regression matrix passes, but OS-enforced production process containment is not demonstrated and a real supervisor-self SIGKILL counterexample exists.

## Requirements and evidence

| Gate | Reproduced result | Verdict |
|---|---|---|
| Parent TrainOS v104 integrity | Published ZIP SHA-256 `8f415769350b3e11dee82778befb300938c8d36eee48d9c1b8d84f4c93415dad`; 4,887 base files present; only four deliberate modifications | PASS |
| 24 functional domains | 24 distinct domains in runner registry | PASS |
| Three strict full pytest runs | 3/3, each **1,514 passed**, exit 0 | PASS |
| Three strict joint recovery/CI/diagnostics runs | 3/3, each **419 passed**, exit 0 | PASS |
| Default ordered serial per-file Runner | **955/955** file starts, 24/24 domains, exit 0, `ALL CONFIGURED STAGES PASSED`; 2168.85 sec | PASS |
| Four-worker isolated per-file Runner | **955/955** file starts, 24/24 domains, exit 0, completion marker; 798.17 sec | PASS |
| Batch per-domain Runner | **24/24** batches, 24/24 domains, exit 0, completion marker; 172.007 sec | PASS |
| Mode-specific independent supervisor | All 3 returned 0 and `cleanup_complete=true`, empty residual running PID lists | PASS for these observations |
| SQLite WAL concurrency | 8 independent stress iterations with 32 threaded and 16 process calls each, one committed journal; strict regression passes | PASS in tested environment |
| Real SIGTERM / runner timeout | Supervisor exit 143 / 124, independent cleanup verified | PASS for these probes |
| Real SIGKILL Runner with detached child | pidfd-supervisor cleans descendant | PASS for this probe |
| Real SIGKILL Supervisor with detached child | Runner and child **remain alive** until external independent subreaper cleanup | **COUNTEREXAMPLE / NO-GO** |
| PID1 and writable cgroup v2 | PID1=`supervisord`; cgroup v2 mounted read-only; delegation fails `EROFS` | **BLOCKED** |
| OS-enforced production admission / legacy fencing | `--production` and direct `TRAINOS_KERNEL_PRODUCTION=1` reject startup; ordinary same-UID direct legacy invocation is not OS-fenced | **BLOCKED** |
| ResourceWarning and DeprecationWarning as errors | Explicit error filters for all strict pytest and kernel cases; independent 2-failure negative-control test passes | PASS |
| Cross-UID adversarial boundary / hardware integration | Not available in this container; no independent end-to-end proof | **BLOCKED** |

## Evidence policy

Every test attempt has separate `.json`, `.stdout.log`, `.stderr.log`, `.exitcode`. The expected warning negative control intentionally stores a failing pytest exit code; this is **not** a passing full regression. All archived v104 failed attempts are still present, unchanged, alongside v105 evidence. The local success of per-file modes does not establish safety of real TrainOS-managed production trains, payment systems or physical SnowPiercer subsystems.

## Required next work

v106 must obtain an independently provisioned cgroup v2 delegation and an OS service authority that outlives the supervisor. Demonstrate fail-closed cgroup kill after SIGKILL of the supervisor, PID reuse defenses for remaining PGID operations, direct legacy production fencing under different UIDs, and production admission with independent attestation. Re-run full regressions and maintain NO-GO until independent validation.
