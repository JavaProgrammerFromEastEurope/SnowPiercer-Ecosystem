# TrainOS v103 — requirements and acceptance criteria

| ID | Requirement | Evidence / criterion |
|---|---|---|
| TR-103-01 | Preserve previous functional areas and source/API surface | Pinned registry; comparison to verified v102 archive, 24 domains |
| TR-103-02 | Bound individual pytest executions without buffering full output in RAM | Kernel Runner tempfiles, timeout configuration and timeout test |
| TR-103-03 | Fail closed on leftover descendants after pytest leader exit | residual group returns 125, SIGTERM/SIGKILL cleanup test |
| TR-103-04 | Protect active subprocess on runner SIGTERM | main-thread termination handler and isolated SIGTERM test |
| TR-103-05 | Investigate runner SIGKILL under Linux supervisor | independent negative test and limitation recorded |
| TR-103-06 | Preserve serial default; optionally improve per-file throughput | `TRAINOS_KERNEL_WORKERS` opt-in, default=1, stage barrier tests |
| TR-103-07 | Reproduce v101 combined regressions in v103 | Three complete strict combined runs, each reported independently |
| TR-103-08 | Validate entire TrainOS test suite | strict full pytest with ResourceWarning, DeprecationWarning and pytest unraisable as errors |
| TR-103-09 | Complete and compare Kernel Runner modes | default serial and batch, or clearly distinguish opt-in per-file workers from default |
| TR-103-10 | Preserve all failures and build reproducible evidence | stdout, stderr, exit codes, timeout and environment metadata |
| TR-103-11 | Produce cumulative source artifact with SHA-256 verification | archive and JSON manifest excluding itself |
| TR-103-12 | Fail closed on missing production crash/UID/PID1 evidence | always BLOCKED / NO-GO until independent end-to-end confirmation |

No successful test is to be interpreted as proving unrelated physical-system readiness.
