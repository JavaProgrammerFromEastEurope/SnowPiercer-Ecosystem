# TrainOS v104 — preserved failures and evidence boundaries

## Exploratory supervisor test (before verification harness)

The first local isolated pytest run completed `5 passed, 1 failed`.
`test_killed_runner_detached_descendant_cleanup` tried to inspect the
nonportable `/proc/<pid>/task/<pid>/children`, which does **not** exist in the
current Linux procfs. This was a defect in the **test**, not in the supervisor.
The test was fixed to enumerate and validate PPID relationships via
`/proc/<pid>/stat`. The next strict local run completed `6 passed`, and the
unique evidence-producing focused run completed `15 passed`.

The initial exploratory run was captured in the interactive terminal output
only, not in a dedicated stdout/stderr file; it is NOT treated as an
independently archived regression run. The subsequent focused verification
report and stdout/stderr are saved as `focused_1.*`. This limitation is not
concealed.

## Strict full #3 and #4: each 1 FAILED, 1,504 PASSED

During an additional concurrent process-fanout stress, the third complete
strict full test run reported:

`tests/ledger_contract/test_financial_ledger.py::test_concurrent_identical_retries_commit_once`

Failure: `sqlite3.OperationalError: database is locked` while
`kernel/economy/ledger_contract/store.py` applied `PRAGMA journal_mode=WAL`
under eight concurrent ledger constructors.

Artifacts: `strict_full_3.*` and `strict_full_4.*`, each preserving stdout, stderr, JSON and exit code.
The failure was NOT hidden, renamed as PASS, or excluded from the broad suite.
Strict full runs #1, #2 and #5 passed 1,505 tests each. The two failures
#3 and #4 remain visible even though three other runs passed. The existing
financial-ledger locking race is a separate outstanding TrainOS issue and
further supports BLOCKED/NO-GO.

## Negative warning control

`warning_negative_control.*` intentionally returns exit code 1 after two
expected pytest failures, to demonstrate that ResourceWarning and
DeprecationWarning are errors. The JSON marks its **negative control test**
as PASS, but it is not a passing regression run.

## Process limitations

A hostile or crashed supervisor cannot guarantee cleanup of descendants
without an independent OS cgroup/service-manager authority. `CGROUP_PID1_PROBE_V104.json`
records a real failed attempt to create a delegated cgroup (`EROFS`).
No cross-UID or production PID1 certification is inferred from these tests.

## Kernel 4-worker attempt #1: two per-file test failures

`kernel_workers_1.*` completed with exit code 1, and is preserved as FAIL.
The stage barrier stopped execution after `ci_release`; this is NOT a complete
24-domain worker-mode PASS. The two failing files were:

- `tests/domains/ci_release/test_bounded_pytest_v94.py`: expected
  `group_sigkill` during a TERM-resistant timeout, but the recorded group
  cleanup path was `['timeout', 'group_sigterm', 'group_absent']`. A fork/exec
  signal-handler registration race under multiple simultaneous pytest
  processes may explain the difference. This is **not** proof that all cleanup
  expectations are met.
- `tests/domains/ci_release/test_kernel_runner_v102.py`: immediately sampled
  the child `/proc/.../stat` after runner timeout and observed `R` rather than
  `Z`. This can occur before asynchronous signal delivery is visible; the test
  lacks bounded polling, unlike the stronger v103 test. A ResourceWarning
  from the fixture's unclosed temporary file also appears in stdout.

Neither failed file was silently ignored. The actual returned status,
stdout/stderr and independent supervisor report remain under
`kernel_workers_1.*`. Additional worker attempts, if performed, use new
iteration numbers and will not replace this failure.
