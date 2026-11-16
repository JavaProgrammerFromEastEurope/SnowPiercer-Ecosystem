# Stage 558 — Capture the last observed and last completed pytest test

This stage adds a focused contract for the full-suite pytest diagnostic runner in `scripts/ci/run_pytest_diagnostic.py`.

## Acceptance

- Capture the last observed and last completed pytest test.
- Diagnostic JSON remains deterministic and machine-readable.
- A timeout is reported as `INCOMPLETE_TIMEOUT`, never as a pass or an assertion failure.
