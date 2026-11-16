# TrainOS Stage 112 — Ambiguous COMMIT During Attempt Creation

## Goal

Handle ambiguous SQLite commit outcomes for `begin_attempt()` without creating duplicate recovery attempts or incrementing an authorized retry more than once.

## Implementation

- `begin_attempt()` now snapshots the full intended journal row before committing and passes that exact state to the Stage 111 fresh-connection resolver.
- The resolver treats a commit exception as success only when a new SQLite connection reads a row matching every persisted column, including owner UUID, fencing token, attempt count, lease, status, and authorization fields.
- The interrupted-owner transition (`IN_PROGRESS` to `FAILED`) also resolves an ambiguous commit before returning the expected explicit-authorization block.
- Unconfirmed results remain fail-closed; ordinary pre-commit failures roll back and leave no new attempt.

## Regression coverage

- New-attempt creation commits but reports an acknowledgement error; the caller receives the durable attempt and a reopened store does not create a duplicate.
- An explicitly authorized retry commits but reports an acknowledgement error; attempt count and fencing token advance exactly once, and restart/retry cannot duplicate the transition.
- A failure before the underlying commit leaves no row and a subsequent clean attempt succeeds.

## Limitations

These tests simulate SQLite API-level acknowledgement ambiguity, not physical power loss, filesystem corruption, storage-controller behavior, or hardware-in-loop operation. This stage does not establish production safety or certification.
