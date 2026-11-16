# TrainOS v65 — Regression and CI Policy

## Release range

- New stages: 558–567.
- Unified regression: stages 170–567 inclusive.
- CI stage matrix: continuous, non-overlapping coverage of stages 1–567.

## Full-suite diagnostic policy

The full-suite runner uses verbose pytest output and a hard timeout. It records the command, elapsed time, timeout budget, bounded log tail, last observed test, last completed test, and outcome counts in JSON. It writes the JSON atomically and preserves the full log as a separate artifact.

`INCOMPLETE_TIMEOUT` is not equivalent to `FAIL` (an observed nonzero pytest exit) or `PASS` (pytest exit code zero). A timeout must not be described as proof of an assertion failure, a deadlock, or a successful suite. The last observed test is a progress marker only; it does not independently establish causation.

## Evidence from this release

- Stages 558–567: 10 passed.
- Unified regression stages 170–567: 428 passed.
- Supporting checks (`tests/ci`, `tests/ledger_contract`): 70 passed.
- Python AST audit: 3,063 files scanned, 0 syntax errors.
- Workflow YAML parse: passed.
- Local full-suite diagnostic: `INCOMPLETE_TIMEOUT` after 20 seconds, last observed test at stage121. A separate preliminary run reached stage159 at approximately 45 seconds. This is consistent with a global time budget too short to characterize the full suite; it does not establish stage137 as the root cause. The full suite remains unverified in this environment.
- Hosted GitHub Actions: not run here.
- External payment sandbox: NO-GO / not verified.
