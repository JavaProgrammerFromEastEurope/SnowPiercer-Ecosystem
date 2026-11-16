# TrainOS v105 — architecture, requirements and contracts

## API and lineage
Keep `KernelTestRunner.run`, `_run_test`, `_run_batch`, `_execute`, 24 functional domains, and the existing `FinancialLedger(database=..., timeout_seconds=...)` signature. Preserve all v104 files unless a deliberate fix modifies them and retain historical evidence byte-for-byte. Do not mint numeric functional Stages.

## Ledger concurrency
`WAL_ADMISSION`: transient SQLite lock conditions are retried only before the monotonic construction deadline, with `min(25ms, remaining)` waits. Initialization requires WAL mode, synchronous FULL and foreign_keys ON. Unrecoverable errors are re-raised and the connection is closed. Safety admission is **not** a production payments GO.

## Kernel execution
Default serial is ordered, fail-fast, isolated per test file. Worker mode uses a stage barrier and 4 isolated subprocesses; batch runs one pytest per area. No mode substitutes for another. Strict policy: ResourceWarning, DeprecationWarning and pytest unraisable warnings as errors.

## Supervisor authority
v105 development supervisor: Linux subreaper, pidfd process identity, signals, bounded timeouts, adoption/reap, residual-check. Detachment via setsid() must not escape tracked parent-subscription in observed cases. Production `--production` is mandatory-deny while OS-enforced cgroup delegation and independent watcher are absent. `TRAINOS_KERNEL_PRODUCTION=1` direct Runner also denies access; same-UID spoofing is not certified.

## Evidence and production gating
Three independent full strict + three independent joint strict executions, a completed 954+ file serial run and separate worker/batch modes are acceptance targets. All actual exit codes and complete stdout/stderr are recorded. BOOT readiness is NO-GO unless **independent** cross-UID, cgroup/PID1, supervisor-self SIGKILL, rollback/cleanup and physical integration evidence exist.
