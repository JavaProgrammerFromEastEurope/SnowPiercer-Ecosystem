# Stage Matrix Diagnostic — v20

## Scope

This bounded diagnostic runs the ten stage directories 11–20 using `scripts/ci/run_stage_matrix.sh` with a 30-second per-stage timeout. It is not a full-suite result.

## Recorded result

- Stage directories attempted: 10
- PASS: 10
- FAIL: 0
- TIMEOUT: 0
- Runner exit code: 0
- Aggregator exit code with `--check-logs`: 0
- Test count: 100 tests passed across stages 11–20 (10 per stage).
- The TSV, JSON aggregate, and individual logs are stored in `AUDIT/ci_runs/v20_stage11_20/`.

## Additional test attempt

The command `PYTHONPATH=. python -m pytest -q tests/ci tests/ledger_contract tests/stage117 tests/stage118` did not complete within the 480-second command limit in this run. Its output had reached 98% but no final summary was produced. Therefore this run is recorded as **incomplete**, not as a pass. This may reflect the previously observed suite-level long-running behavior; root cause remains unresolved.

## Limitations

- Results cover stages 11–20 only, not all project stages.
- The targeted cross-suite run did not finish within the command limit.
- GitHub Actions was not executed against a remote repository.
- Financial ledger remains a prototype; real payment integration is NO-GO pending independent audit and approved policy decisions.
