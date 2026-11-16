# Stage 529 — Constrain explicit test includes

## Goal
Constrain explicit test includes.

## Implementation
Explicit regression includes must resolve inside the repository root and must be existing Python files.

## Verification
An include outside the project root is rejected with argparse exit code 2.

Run `python -m pytest tests/stage529` from the repository root.
