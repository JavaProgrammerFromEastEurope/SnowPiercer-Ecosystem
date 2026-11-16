# Stage 120 — exact snapshots for ambiguous COMMIT resolution

## Changes

The ambiguous-COMMIT resolver already compares every field in the supplied expected mapping. Two callers (`_finish` and `authorize_retry`) previously supplied only a subset of their updated row. They now read the complete row inside the write transaction and pass the full snapshot to `_commit_or_resolve_ambiguous_result`.

Added tests simulate a commit acknowledgement being lost after the transition commits, followed by an independent connection changing an unrelated field before the resolver verifies durable state. The API must re-raise the original commit exception instead of treating a partial match as confirmed success. Tests cover terminal completion and retry authorization.

## Acceptance criteria

- Expected state is captured before COMMIT while the write transaction is active.
- Resolver accepts an ambiguous COMMIT only if all persisted columns match that snapshot.
- A post-commit row divergence preserves the original exception.
- Restarted readers observe the actual durable state, without pretending the caller received a confirmed success.

## Validation

- Focused tests, Stage 115–120: **12 passed**.
- Full test suite: **734 passed** in 17.45 seconds.
- `python -m compileall -q kernel tests`: passed.
- AST audit: **2,598 Python files**, 0 parse errors.
- ZIP integrity checked after packaging; caches and service directories excluded.

## Limitations

This strengthens local SQLite ambiguity handling. It does not make the journal tamper-proof against privileged database writers and does not establish distributed transaction guarantees or certify TrainOS for transport hardware.
