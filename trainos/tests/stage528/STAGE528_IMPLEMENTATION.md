# Stage 528 — Deterministic regression selection

## Goal
Deterministic regression selection.

## Implementation
Selection is inclusive, sorted, unique, recursive, and restricted to test_*.py files under stage directories.

## Verification
Synthetic directory tree proves ordering, inclusive bounds, and exclusion of helper/non-test files.

Run `python -m pytest tests/stage528` from the repository root.
