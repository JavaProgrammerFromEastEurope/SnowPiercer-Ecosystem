# Stage 417 — End-to-end migrate, backup, restore and UNKNOWN safety

## Goal
End-to-end migrate, backup, restore and UNKNOWN safety.

## Implementation
- Keep the schema version marker fail-closed and tied to verified ledger structure.
- Preserve existing rows and do not silently authorize retries for uncertain external outcomes.
- Ensure failed schema initialization can be corrected and retried without a false current-version marker.

## Acceptance test
Run `pytest -q tests/stage417`. The test checks the stage-specific database invariant using temporary SQLite databases.

## Boundary
These are local SQLite contract tests; they do not prove distributed exactly-once behavior, disaster-recovery objectives, or payment-provider readiness.
