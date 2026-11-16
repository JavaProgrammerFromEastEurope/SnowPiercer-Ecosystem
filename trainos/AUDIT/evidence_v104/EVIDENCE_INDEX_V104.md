# TrainOS v104 — evidence index and meaning

| Artifact prefix / file | Verification purpose |
|---|---|
| `ORIGIN_INTEGRITY_V103.json` | Previous archive SHA-256, ZIP CRC, 4,761 verified manifest members and extracted-file byte equality |
| `SOURCE_DIFF_V104.json` | Cumulative, byte-identical v103 source preservation and added v104 files |
| `strict_full_{1..5}.*` | Independent strict pytest runs of **all tests**, including retained failed runs #3 and #4 |
| `combined_{1..3}.*` | Strict recovery + ci_release + pytest_diagnostics |
| `focused_1.*` | Strict targeted supervisor and Kernel Runner compatibility regressions |
| `kernel_default_1.*` | Strictly sequential ordered fail-fast, one process per file; independent supervisor report |
| `kernel_workers_1.*` | 4-worker opt-in mode, still one pytest process per file; independent supervisor report |
| `kernel_batch_1.*` | One batch per functional domain; independent supervisor report |
| `sigkill_fanout_{1..5}.*` | Five real SIGKILL probes killing the runner with eight detached `setsid()` descendants |
| `SIGKILL_FANOUT_STRESS_SUMMARY_V104.json` | Collated independent probe classifications |
| `ACTUAL_KERNEL_SIGKILL_V104.json` | Real `python -m tests.kernel_runner` SIGKILL with a live pytest child |
| `TERM_ESCALATION_PROBE_V104.json` | SIGTERM-ignoring child; escalation by external supervisor to SIGKILL |
| `WARNING_NEGATIVE_CONTROL_V104.json` | Intentional two-test failure proves ResourceWarning/DeprecationWarning are errors |
| `CGROUP_PID1_PROBE_V104.json` | Actual `EROFS` cgroup creation denial; PID 1 is supervisord |
| `PID_NAMESPACE_PROBE_V104.json` | Actual `EPERM` when trying an independent PID namespace |
| `SAFETY_CASE_V104.md` | Safety contracts, verified boundaries, explicitly unproven guarantees |
| `FAILURE_TRIAGE_V104.md` | Cause and disposition of preserved failed runs |
| `VERIFICATION_SUMMARY_V104.json` | Derived acceptance summary; all nonzero runs retained |
| `SHA256_MANIFEST_V104.json` | Per-file SHA-256 for every ZIP member except the manifest itself |

Each named verification report carries the command, start time, duration,
platform, strict-warning configuration, exit code, stdout path, stderr path,
and relevant source SHA-256 digests. A normal success requires completed
artifacts and exit code 0. A successful **negative** probe may have nonzero
process status by design and must never be counted as a successful full suite.
The release status remains **BLOCKED/NO-GO**, independently of individual
passing tests.
