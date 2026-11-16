# TrainOS v81 — functional recovery migration and bounded pytest

Base: cumulative TrainOS v80 archive.

- Moved ten schema recovery tests from historical `tests/stage398`–`tests/stage407` to `tests/domains/recovery` with pinned assignment removal and an exact migration map.
- Added `scripts/ci/run_bounded_pytest.py`, which runs pytest in a separate process group, applies a wall-clock timeout, signals the process group, escalates to SIGKILL if necessary, and persists merged output and a machine-readable result. On timeout it exits 124. This mitigates unbounded CI hangs but does not prove a particular deadlock root cause.
- Added four contract tests for successful, failed and timed-out pytest executions and migration ownership.
- Combined targeted regression: see `AUDIT/v81_evidence/combined_final.json` and log.
- General collection: see `AUDIT/v81_evidence/collection.log`.
- A strict-warning run printed a passing pytest summary but was interrupted by the parent tool timeout and left no final bounded-runner JSON. Its 66 warnings require separate analysis; this run is not credited as completed evidence.
- Full suite and hosted CI were not executed. No new numbered Stage created.

## Reproduce

`python scripts/ci/run_bounded_pytest.py --timeout 180 --report AUDIT/local_regression.json -- -q tests/domains/recovery tests/domains/ci_release tests/domains/pytest_diagnostics`
