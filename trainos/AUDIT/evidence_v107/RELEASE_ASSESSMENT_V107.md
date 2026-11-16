# TrainOS v107 — cumulative release assessment

**Decision: BLOCKED / NO-GO**. Production isolation and certification not demonstrated.

## Test matrix

| Check | Attempts | PASS | FAIL |
|---|---:|---:|---:|
| strict_full | 6 | 3 | 3 |
| combined | 3 | 3 | 0 |
| focused | 0 | 0 | 0 |
| kernel_default | 1 | 1 | 0 |
| kernel_workers | 1 | 1 | 0 |
| kernel_batch | 2 | 1 | 1 |

## Kernel Runner completeness

Configured 24 domains, 958 per-file starts.

- kernel_default #1: verified_complete=True, files=958, batches=0, domains=24, exitcode=0
- kernel_workers #1: verified_complete=True, files=958, batches=0, domains=24, exitcode=0
- kernel_batch #2: verified_complete=True, files=0, batches=24, domains=24, exitcode=0

## Incomplete/failed verification harness attempts

- strict_full_1: report writing failed, pytest exit code=0; not counted as PASS.
- strict_full_2: report writing failed, pytest exit code=0; not counted as PASS.
- kernel_batch_1: report writing failed, pytest exit code=0; not counted as PASS.

## Preservation

- Parent v106 SHA-256: `f05ad0512dfd6d60f3de1e2dded1a7f05b21912688fc6c20d7552847560d7a20`
- Parent files: 5075, modified: 0, removed: 0, newly added: 129.
- All historical evidence from v106 is preserved, including failed attempts.

## Production blockers

- No independent writable delegated cgroup v2; kernel cgroup.kill and process migration defense unverified
- PID1 is not systemd; watchdog restart after SIGKILL not verified
- Authenticated SO_PEERCRED broker denies every execution: positive production IPC handoff is not implemented
- Direct legacy KernelTestRunner remains callable; OS-level write service fencing not deployed
- No real authority SIGKILL recovery in writable cgroup, no physical-system integration

## Boundary of claims

- Watchdog startup sweep tested by filesystem mocks only, not cgroupfs.
- Actual cross-UID SO_PEERCRED, replay and UID spoof *negative* controls are tested.
- Real SIGKILL supervisor negative control demonstrates process survivors without OS cgroup containment.
- A systemd service prototype is included but not installed, configured, or certified.
- All completed PASS/FAIL logs retained under `AUDIT/evidence_v107`.
