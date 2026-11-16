# TrainOS v106 — cumulative release assessment

**Decision: BLOCKED / NO-GO.** No independent real cgroup v2 containment, cross-UID production boundary, or authority lifetime certificate.

## Executed verification matrix

| Mode | Completed attempts | PASS | FAIL | Evidence |
|---|---:|---:|---:|---|
| strict_full | 4 | 3 | 1 | #1: FAIL exit=1, #2: PASS exit=0, #3: PASS exit=0, #4: PASS exit=0 |
| combined | 3 | 3 | 0 | #1: PASS exit=0, #2: PASS exit=0, #3: PASS exit=0 |
| kernel_default | 1 | 1 | 0 | #1: PASS exit=0 |
| kernel_workers | 1 | 1 | 0 | #2: PASS exit=0 |
| kernel_batch | 1 | 1 | 0 | #2: PASS exit=0 |

### Full and joint regression completeness

- Full strict regression requires >= 3 independent successful completed runs; **CONFIRMED**.
- Joint recovery + CI + pytest_diagnostics requires >= 3 successful runs; **CONFIRMED**.
- Explicit warning negative control produced 2 intentionally failed tests (exit=1); this does not count as a release failure.

### Kernel Runner mode checks

- Registered functional areas: **24**. Configured per-file test starts: **956**.
- Batch executes a different process-isolation contract from serial/worker; none substitute for another.
- kernel_default #1: **COMPLETE**; exit=0, domains=24, per-file starts=956, batches=0, supervisor cleanup=True, duration=2393.484s.
- kernel_workers #2: **COMPLETE**; exit=0, domains=24, per-file starts=956, batches=0, supervisor cleanup=True, duration=1054.416s.
- kernel_batch #2: **COMPLETE**; exit=0, domains=24, per-file starts=0, batches=24, supervisor cleanup=True, duration=343.909s.

## v105 source compatibility and archive lineage

- All v105 archive files retained; final ZIP build enforces zero deletions and verifies every SHA-256 entry.
- Four executable script modes restored after Python ZIP extraction; historical bytes unchanged.
- Failure `strict_full_1` is retained: 1,521 passed and 1 failed due to missing execute mode on run_stage_matrix.sh.
- New v106 authority and probes are additive; `KernelTestRunner` legacy signatures unchanged.

## Process and production safety boundaries

- v106 authority provides a fork gate before exec, pidfd identity of its supervised child and a cgroup.kill cleanup protocol.
- Only unit tests of cgroup.kill and fail-closed host admission executed here: host cgroup v2 read-only, no delegated subtree.
- Real SIGKILL supervisor negative control: Runner and double-fork detached child survived; external independent probe cleaned both.
- Runner SIGTERM (143) and SIGKILL (137) probes passed with v105 development supervisor cleanup; SIGTERM supervisor (143) and timeout (124) also passed.
- Actual cross-UID probes under numeric UIDs 65534 and 65533 rejected production; development legacy invocation remains available. This is NOT OS-enforced legacy fencing.
- Concurrent production admission: 16 attempts denied without command execution. This does NOT prove successful admission races.
- pidfd presence/identity is proven for observed direct processes only; independent authority cgroup lifecycle requires real external verification.
- SIGKILL of authority itself and service-manager restart behavior were not proven.
- Physical SnowPiercer integration and safety certification are outside the demonstrated boundary.

## Decision and next steps

**BLOCKED/NO-GO** until an independently controlled writable cgroup v2, real supervisor/authority crash testing, peer-authenticated cross-UID production broker, OS-level legacy fencing and physical subsystem safety evidence are available.

All stdout, stderr, exit codes, JSON outcomes, including failures, are retained under `AUDIT/evidence_v106/`.
