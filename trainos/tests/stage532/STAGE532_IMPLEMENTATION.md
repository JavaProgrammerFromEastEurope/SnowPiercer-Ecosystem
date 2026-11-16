# Stage 532 — Validate timeout configuration

## Goal
Validate timeout configuration.

## Implementation
Invalid timeout values are rejected before starting a test process.

## Verification
A zero-second timeout is rejected with argparse exit code 2.

Run `python -m pytest tests/stage532` from the repository root.
