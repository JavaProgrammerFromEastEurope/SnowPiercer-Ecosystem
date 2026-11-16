# TrainOS v102 — verification record

Status: BLOCKED / NO-GO. No production readiness claim.

## Source audit
Base: user-provided TrainOS-v101-source.zip. Functional domain registry and legacy assignments retained. The default runner executes per test file, with optional TRAINOS_KERNEL_BATCH=1 behavior retained.

## Changes
- tests/kernel_runner/runner.py: bounded pytest subprocess runtime; bounded stdout/stderr memory via temporary files; POSIX process-group SIGTERM and SIGKILL on timeout; cleanup on exceptions; return 124 for timeout.
- tests/domains/ci_release/test_kernel_runner_v102.py: success/failure/timeout/descendant cleanup/config tests.

## Executed evidence
- First broad combined strict regression was interrupted after failures; see combined_1.stdout.log and combined_1.exitcode (143). This is NOT a completed regression. No claim of all-suite success.
- First isolated run had a flaky race (pid file absent before short timeout), preserved as runner_1.stdout.log. The timeout in the test was increased; three subsequent strict isolated runs succeeded, see verified_{1,2,3}.*.
- Strict settings: PYTHONWARNINGS=error::ResourceWarning,error::DeprecationWarning.

## Outstanding
- Complete three broad joint regressions for recovery, ci_release, pytest_diagnostics.
- Complete standard per-file Kernel Runner and compare against batch.
- Full TrainOS regression and regression selector.
- Independent evidence for cross-UID security, SIGKILL crash points, orphan-free behavior in production deployment, and library compatibility across all APIs.

A green focused test does not establish these requirements. BLOCKED/NO-GO remains mandatory.
