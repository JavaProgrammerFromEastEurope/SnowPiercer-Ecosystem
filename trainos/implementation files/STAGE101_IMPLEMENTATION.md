# TrainOS Stage 101 — Recovery ownership race regression

## Scope

Added regression coverage for recovery journal operations performed through independent SQLite connections. The tests verify that a caller with a mismatched run identity cannot finish another owner's attempt, and that a failed terminal-state update rolls back without losing the active owner identity or changing its fencing token.

## Safety properties checked

- Ownership is checked against durable run ID and fencing token, not just an attempt key.
- A rejected stale result leaves the current attempt `IN_PROGRESS` and preserves its owner metadata.
- A SQLite trigger simulates a terminal-state write failure; rollback preserves the in-progress state and allows the current owner to retry the journal transition.
- Successful completion is still possible after the injected failure is removed.

## Validation

Validation results are recorded in the Stage 101 completion response after running focused and full test suites, compilation, syntax audit, and archive integrity checks.

## Limits

This stage does not make the journal tamper-proof or provide distributed leases. The legacy tokenless finish API still accepts same-process callers for compatibility; safety-critical integrations should always pass both `owner_run_id` and `fencing_token`. A fencing token only protects resources that independently enforce it; it cannot stop stale code from performing unrelated external side effects.
