# TrainOS Stage 100 — Recovery ownership fencing

## Scope

Stage 99 used PID liveness as a same-host guard, which does not distinguish process incarnations after PID reuse and does not provide a durable ownership generation. This stage adds a random owner-run identity and a monotonically increasing fencing token to the recovery-attempt journal.

## Implementation

- Added `owner_run_id` and `fencing_token` columns with a forward-compatible SQLite migration.
- Each initial attempt receives a unique owner-run ID and fencing token `1`; each explicitly authorized retry receives a new owner-run ID and increments the token.
- `finish_success` and `finish_failure` accept both ownership values and reject stale identities/tokens. Legacy calls without explicit tokens are restricted to the currently recorded local PID for compatibility.
- Startup recovery passes the ownership values returned by `begin_attempt`; crash-window reconciliation uses the journaled identity only after validating the backup and candidate against the anchor.
- Added tests for stale-owner rejection and migration from the prior schema.

## Limitations

The token fences journal state transitions, but it is not by itself a distributed lock and cannot stop a stale process from performing external side effects unless every relevant resource also enforces the token. Legacy tokenless calls remain a compatibility path and should be migrated to explicit owner tokens. This is not a safety certification or real-hardware validation.
