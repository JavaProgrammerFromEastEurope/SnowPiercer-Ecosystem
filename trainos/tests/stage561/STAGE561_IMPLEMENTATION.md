# Stage 561 — Validate log-tail limits

This stage adds a focused contract for the full-suite pytest diagnostic runner in `scripts/ci/run_pytest_diagnostic.py`.

## Acceptance

- Validate log-tail limits.
- Diagnostic JSON remains deterministic and machine-readable.
- A timeout is reported as `INCOMPLETE_TIMEOUT`, never as a pass or an assertion failure.
