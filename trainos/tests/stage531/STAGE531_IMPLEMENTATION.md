# Stage 531 — Deterministic dry-run output

## Goal
Deterministic dry-run output.

## Implementation
Dry-run reports the exact sorted unique file selection without invoking pytest.

## Verification
Duplicate explicit include is de-duplicated and output remains machine-readable.

Run `python -m pytest tests/stage531` from the repository root.
