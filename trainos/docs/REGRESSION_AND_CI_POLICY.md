# TrainOS Regression and CI Policy

## Deterministic selection
Run `python scripts/ci/run_regression.py --start 170 --end 537 --timeout-seconds 1800 --report test-logs/regression-170-537.json`. The selector includes recursively discovered `test_*.py` files in inclusive `tests/stageN` directories, sorted and de-duplicated. Explicit include paths must resolve inside the repository and be Python files.

## Timeouts and evidence
A timed-out pytest subprocess returns exit code 124 and writes `result: TIMEOUT`, elapsed time, timeout value, selected paths, and any captured partial output to the JSON evidence file. Timeout is a failed/incomplete check, never a pass.

## CI shards
GitHub Actions isolates stage directories using `scripts/ci/run_stage_matrix.sh` with a per-stage timeout. Every stage range must cover stages 1 through the latest release stage without gaps or overlap. Hosted results must be linked or explicitly marked `NOT_RUN`.

## Acceptance
A release is not called fully tested unless the selected regression, supporting checks, syntax audit, archive integrity, and complete suite status are explicitly recorded. Physical readiness and external payment safety require separate domain-specific evidence.
