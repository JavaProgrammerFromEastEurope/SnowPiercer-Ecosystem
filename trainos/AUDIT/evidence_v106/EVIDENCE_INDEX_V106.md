# TrainOS v106 — evidence index

**Release decision: BLOCKED / NO-GO.** No real cgroup v2 authority end-to-end test or OS-enforced cross-UID production fencing is available in this environment.

## Proven execution outputs

- `PARENT_V105_INTEGRITY.json`: independently checked original v105 ZIP against all 4,971 SHA-256 manifest entries.
- `ZIP_MODE_RESTORATION_V106.json`: four original executable script modes restored from v105 ZIP metadata; first `strict_full_1` FAIL and its raw stdout/stderr/exitcode are intentionally retained.
- `strict_full_{1,2,3,4}.{json,stdout.log,stderr.log,exitcode}`: first FAIL due to lost mode; three subsequent complete PASS runs, 1,522 tests each.
- `combined_{1,2,3}.{json,stdout.log,stderr.log,exitcode}`: three independent strict recovery+CI+diagnostics PASS runs, 427 tests each.
- `focused_1.*`: 22 PASS tests of new authority and retained Kernel Runner / ledger contracts.
- `kernel_default_1.*`, `kernel_workers_2.*`, `kernel_batch_2.*`: successful 24-area runs with separate stdout/stderr/exitcode and `.supervisor.json` (all supervisor cleanup PASS, no residual running PIDs). Per-file count 956 for serial and worker; 24 batches for batch.
- `WARNING_NEGATIVE_CONTROL_V106.json` + `warning_negative_control.*`: two intentional pytest failures prove `ResourceWarning`/`DeprecationWarning` strict policy.

## Process safety, deliberately non-certifying outputs

- `CGROUP_HOST_PROBE_V106.json`, `CGROUP_EROFS_NEGATIVE_V106.json`: read-only kernel cgroup v2 and real EROFS on delegation attempt.
- `DOUBLEFORK_SUPERVISOR_SIGKILL_V106.json`: *negative* real SIGKILL control; root and detached grandchild survived; independent subreaper killed/reaped them, cgroup.kill **NOT TESTED**.
- `RUNNER_SIGNAL_PROBES_V106.json`, `RUNNER_{sigterm,sigkill}_SUPERVISOR_V106.json`: real Runner SIGTERM=143 and SIGKILL=137 with supervised detached-child cleanup.
- `PROCESS_BOUNDARY_PROBES_V106.json`, `SIGTERM_SUPERVISOR_V106.json`, `TIMEOUT_SUPERVISOR_V106.json`: real SIGTERM supervisor=143 and timeout=124 with development cleanup.
- `CROSS_UID_LEGACY_PROBE_V106.json`: two numeric UIDs tested. Production admission denied; legacy development Runner invocation still succeeds without production flag.
- `ADMISSION_RACE_NEGATIVE_V106.json`: 16 concurrent denial-only production attempts, none executed a command.
- `MODES_LAUNCHER_HANDOFF_V106.json`: detached serial verifier remained running after launcher shell was stopped to avoid redundant workers; completion verified by its own independent records.

## Reproduction and safety contracts

- `ARCHITECTURE_REQUIREMENTS_V106.md`, `SAFETY_ANALYSIS_V106.md`, `REPRODUCE_V106.md`.
- `VERIFICATION_SUMMARY_V106.json`, `RELEASE_ASSESSMENT_V106.md`, `SHA256_MANIFEST_V106.json` generated after evidence completion.
- All v105 and earlier evidence remains cumulative and unchanged. Success of development regression suites does not justify production GO.
