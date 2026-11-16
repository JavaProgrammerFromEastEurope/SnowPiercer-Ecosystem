# TrainOS Stage 84 — Atomic trusted event reads

## Change

Trusted reads from `CommandEventStore.get_events()` and `all_events()` now perform the recovery-gate assessment and event retrieval under the same re-entrant store lock and, when the store owns no existing transaction, the same SQLite read transaction. This closes the in-process check-then-read gap and gives the event database a consistent read snapshot across integrity verification and payload retrieval. A rejected gate rolls back the transaction it opened. Legacy mode remains unchanged and does not open a read transaction solely for retrieval.

## Tests

- Confirm the SQLite transaction is active before the trust assessment runs.
- Confirm a missing anchor fails closed and leaves no transaction open.
- Confirm trusted payload retrieval returns the expected event and leaves no transaction open.
- Confirm legacy untrusted reads retain their previous transaction behavior.

## Security boundary

This is an application-level consistency improvement, not a complete trust boundary. The separate anchor database can still be changed by an actor who can modify it; direct access to internal SQLite connections and integrity metadata is not prevented. Existing transactions supplied by a caller remain caller-managed. Neither this stage nor the event-log chain is safety-certified or suitable by itself for controlling train movement, braking, or levitation.
