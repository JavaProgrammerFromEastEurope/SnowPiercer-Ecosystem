# Stage 115 — Ambiguous COMMIT During Lease Renewal

## Scope

`renew_lease()` now uses the existing fresh-connection durable-state resolver for its commit boundary. Before commit, it snapshots the complete intended journal row; if `commit()` raises, the operation is considered successful only if a separate SQLite connection observes the exact expected row. A pre-commit failure or an unverified state remains an error.

## Regression coverage

- Simulated successful durable commit followed by a lost acknowledgement, verified again after reopening the journal.
- Simulated failure before the commit reaches SQLite; the durable lease remains unchanged and the connection is reusable.
- SQLite trigger aborts lease update; transaction rolls back and a later valid renewal succeeds.

## Validation

See the stage handoff for exact focused and full-suite test results. These are SQLite/API-level fault simulations, not physical power-loss or filesystem fault-injection tests. TrainOS is not certified for real-world train control.

### Verified run

- Focused Stage 115 + Stage 110 + Stage 112 tests: **12 passed**.
- Full suite: **725 passed in 23.78 seconds**.
- `python -m compileall -q kernel tests`: passed.
- AST parse audit: 2,593 Python files, zero parse errors.
- ZIP integrity check: passed; archive excludes `.git`, virtual environments, Python/pytest caches, `.history`, `.DS_Store`, and `__MACOSX`.
