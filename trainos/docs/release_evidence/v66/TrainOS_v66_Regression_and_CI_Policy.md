# TrainOS v66 — Regression and CI Policy

- Release stages: 568–577 inclusive.
- Unified regression: stages 170–577 inclusive.
- CI stage matrix: continuous, non-overlapping numeric coverage of stages 1–577.
- Full-suite diagnostic: preserve verbose log, collection count, last observed/completed node IDs, outcome counts, elapsed time, and bounded tail; write JSON atomically.
- Pytest import-mode output can insert a `<- source/path.py` annotation between a node ID and its outcome. The diagnostic parser explicitly handles this form so observed PASS/FAIL counts and the last completed test are not silently lost.
- `PASS`, `FAIL`, and `INCOMPLETE_TIMEOUT` remain distinct. An outer execution interruption without a child exit status is recorded as incomplete; no final pass/fail count is inferred from partial progress.

## Verification evidence

- Stages 568–577: 10 passed; per-stage matrix 10/10 PASS, zero failures/timeouts.
- Unified regression stages 170–577: 439 passed across 408 test files.
- Supporting checks (`tests/ci`, `tests/ledger_contract`): 70 passed.
- Collection: 1,397 tests collected successfully.
- Python AST audit: 3,073 files scanned, zero syntax errors.
- Workflow YAML parsing and numeric matrix coverage: PASS.
- Full suite: INCOMPLETE_TIMEOUT. The local execution environment interrupted the verbose attempt after progress into stage178; 359 completed PASS outcomes were recoverable from the log, with zero observed failures. This is not a final suite result and does not establish a stage-specific defect.
- Hosted GitHub Actions: NOT RUN / UNVERIFIED.
- External payment provider sandbox: NO-GO / NOT VERIFIED.
