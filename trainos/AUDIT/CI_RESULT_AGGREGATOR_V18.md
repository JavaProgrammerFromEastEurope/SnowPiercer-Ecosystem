# CI Result Aggregator — v18

## Change

Added `scripts/ci/summarize_stage_results.py`, a standard-library-only consumer for the TSV summary emitted by `scripts/ci/run_stage_matrix.sh`.

The aggregator validates the exact TSV header, field types, allowed statuses, stage uniqueness, status/exit-code consistency, safe log filenames, and optionally the presence of every referenced log. It prints an aggregate count and can write a machine-readable JSON report. Exit codes are `0` for all-PASS summaries, `1` when valid results contain FAIL/TIMEOUT, and `2` for malformed or missing input.

Added six unit tests in `tests/ci/test_summarize_stage_results.py` for mixed results, empty input, duplicate stages, inconsistent status/exit code, missing logs, and JSON round-tripping.

## Verification performed in this environment

- `python -m unittest tests/ci/test_summarize_stage_results.py -v`: **6 passed**.
- `./tests/ci/test_run_stage_matrix.sh`: **PASS**, including simulated PASS/FAIL/TIMEOUT classification.
- `PYTHONPATH=. python -m pytest -q tests/ci/test_summarize_stage_results.py tests/ledger_contract tests/stage117 tests/stage118`: **73 passed**.
- Real stage runner smoke test for stages 117–118, 60-second per-stage timeout: **2/2 stages PASS** (stage117: 2 tests; stage118: 1 test).
- Aggregator consumed that real `summary.tsv` with `--check-logs` and emitted valid JSON: **PASS**.

## Scope and limitations

This is a targeted verification, not a full-suite result. The complete test suite has not been confirmed green; prior full-suite runs timed out and the root cause remains unresolved. GitHub Actions was not executed against the remote repository in this environment. Financial-ledger integration with real payments remains **NO-GO** pending independent review and explicit policy approval.
