# Stage 444 — Concurrent backup publication

## Scope

Starts two publishers against the same destination. Exactly one succeeds, the other receives FileExistsError, and the published database validates.

## Contract

Same-destination concurrency must not clobber a winning backup.

## Verification

Automated test: `tests/stage444/`. The release manifest records the aggregate targeted and regression test results.
