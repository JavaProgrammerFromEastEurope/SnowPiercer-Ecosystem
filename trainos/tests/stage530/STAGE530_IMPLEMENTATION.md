# Stage 530 — Persist timeout evidence

## Goal
Persist timeout evidence.

## Implementation
Regression runner accepts a positive hard timeout and writes structured TIMEOUT evidence with exit code 124 and captured partial output.

## Verification
A simulated subprocess timeout produces a JSON report and exit code 124.

Run `python -m pytest tests/stage530` from the repository root.
