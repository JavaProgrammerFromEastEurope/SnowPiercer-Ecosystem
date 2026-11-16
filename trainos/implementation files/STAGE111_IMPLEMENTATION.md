# TrainOS Stage 111 — Ambiguous SQLite COMMIT Results

## Goal
Resolve the case where SQLite durably commits a recovery-journal transition but the caller receives an exception from the `commit()` call. A commit exception alone is not treated as proof of rollback.

## Implementation
- Added `_commit_or_resolve_ambiguous_result()` to `EventLogRecoveryAttemptStore`.
- On commit exception, roll back only if the original connection still reports an open transaction.
- Open a separate SQLite connection and verify the durable row against the exact expected state before treating the transition as successful.
- If the expected state cannot be independently confirmed, preserve and re-raise the original commit exception. This keeps the behavior fail-closed.
- Applied this resolution to terminal attempt transitions and explicit retry authorization. The resolution does not bypass owner UUID/fencing-token validation or candidate verification in the higher-level recovery workflow.

## Regression coverage
- Simulated a commit that succeeds on the underlying SQLite connection and then raises an acknowledgement error.
- Verified `finish_success()` resolves the ambiguous result from a fresh connection and that a restarted store sees `SUCCEEDED`; a repeated transition is not performed.
- Verified retry authorization similarly resolves only when the durable `RETRY_AUTHORIZED` state and operator/reason metadata match.
- Existing pre-commit failure, trigger-abort, rollback, and stale-owner tests remain in place.

## Scope and limitations
The tests inject an acknowledgement-loss condition around SQLite's commit API. They are not physical power-loss, filesystem, storage-controller, or hardware-in-loop tests. This is not a claim of production safety certification.
