# TrainOS v105 evidence index

## Machine-verifiable source and release lineage
- `VERIFICATION_SUMMARY_V105.json`: matrix outcomes, mode log count verification, lineage comparison, counterexamples, blockers
- `SHA256_MANIFEST_V105.json`: SHA-256 per-file manifest; excludes only itself to avoid a circular hash
- `CGROUP_PID1_PIDFD_PROBE_V105.json`: Linux OS process authority preflight and actual `EROFS`
- `SUPERVISOR_SELF_SIGKILL_NEGATIVE_CONTROL.json`: observable supervisor-self kill counterexample with external cleanup

## Regression attempts
- `strict_full_{1,2,3}.{json,stdout.log,stderr.log,exitcode}`: three complete strict pytest runs
- `combined_{1,2,3}.{json,stdout.log,stderr.log,exitcode}`: three joint recovery/CI/diagnostics runs
- `focused_1.*`: focused v105 boundary and API compatibility
- `kernel_default_1.*`, `kernel_workers_1.*`, `kernel_batch_1.*`: three modes, plus each `.supervisor.json`

## Negative controls and stress
- `WARNING_NEGATIVE_CONTROL_V105.json` with `warning_negative_control.*`: intentional two-failure warning run
- `PROCESS_BOUNDARY_PROBES_V105.json`, `SIGTERM_SUPERVISOR_V105.json`, `TIMEOUT_SUPERVISOR_V105.json`: real signal, timeout and legacy production refusal
- `WAL_CONCURRENCY_STRESS_V105.json`, `wal_stress.*`: eight rounds of concurrent ledger admission and integrity
- `SAFETY_CASE_V105.md`, `ARCHITECTURE_CONTRACT_V105.md`, `REPRODUCE_V105.md`, `NEXT_RELEASE_V106.md`

**Warning:** green software checks coexist with independent production NO-GO. Do not treat `cleanup_complete=true` for live supervisor as evidence of safe operation after its own SIGKILL.
