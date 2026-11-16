# Stage 563 — Keep successful reports free of timeout warnings

This stage adds a focused contract for the full-suite pytest diagnostic runner in `scripts/ci/run_pytest_diagnostic.py`.

## Acceptance

- Keep successful reports free of timeout warnings.
- Diagnostic JSON remains deterministic and machine-readable.
- A timeout is reported as `INCOMPLETE_TIMEOUT`, never as a pass or an assertion failure.
