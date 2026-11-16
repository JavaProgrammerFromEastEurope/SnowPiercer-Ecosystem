# Stage 154 — Cross-journal execution consistency

Added `ExecutionJournalConsistencyChecker`, a read-only fail-closed diagnostic gate comparing a command idempotency record with its bound execution's append-only audit history.

- A `claimed` idempotency record paired with `created` or `running` execution is consistent.
- A `completed` record paired with a `completed` execution is consistent.
- Unknown outcomes, missing execution history, and terminal disagreement require explicit reconciliation or are reported as conflicts.
- Legacy unbound idempotency records are explicitly marked `unbound` and never authorize dispatch.
- The checker never repairs records and never authorizes replay on its own.

The idempotency and execution audit databases are separate SQLite journals and cannot be atomically committed together by this checker. It is a fail-closed diagnostic gate, not a distributed transaction or safety-certified executor.
