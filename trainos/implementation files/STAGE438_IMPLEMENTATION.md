# Stage 438 — Preserve existing backup destinations

## Scope

Verifies backup publication refuses an existing destination rather than replacing a previous snapshot. The test checks the original bytes remain unchanged.

## Contract

Existing destinations are immutable under backup_to(); the no-overwrite behavior is part of the publication contract.

## Verification

Automated test: `tests/stage438/`. The release manifest records the aggregate targeted and regression test results.
