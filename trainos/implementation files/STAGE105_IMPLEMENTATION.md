# TrainOS Stage 105 — Heartbeat-aware startup recovery

## Change

- `EventLogStartupRecovery.run()` now accepts `recovery_lease_seconds` (default 300 seconds) and an optional `recovery_heartbeat_interval_seconds` (default one third of the lease).
- While backup restoration/publication runs, a daemon heartbeat thread renews the current lease using the exact owner UUID and fencing token. The worker is stopped and joined before the journal can transition to a terminal state.
- If renewal fails, recovery fails closed: the candidate is preserved for inspection/reconciliation, the result is `BLOCKED`, and the journal remains `IN_PROGRESS` rather than falsely recording success or failure.
- Lease and heartbeat parameters are validated before a recovery attempt is started. Heartbeats do not change the fencing token.

## Tests

`tests/stage105/test_recovery_lease_heartbeat.py` checks repeated renewal during an operation longer than the lease, fail-closed behavior on heartbeat failure, and invalid timing configuration.

## Limits

The heartbeat protects journal ownership, not arbitrary external side effects. A worker that loses its lease must still avoid un-fenced external operations. This remains a local SQLite-based mechanism, not distributed consensus or train-control certification.
