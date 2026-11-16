# Stage 177 — Multi-generation reconciliation after prolonged outages

## Scope

This stage adds regression coverage for multiple dispatch generations, repeated lost acknowledgements, and stale reconciliation evidence after a prolonged outage. It verifies that each `not_executed` record remains associated with its generation and that old evidence cannot authorize recovery of a later attempt.

## Tests

- Repeatedly reserves, marks the outcome unknown, and reconciles three dispatch generations.
- Reopens the SQLite store and verifies the full ordered evidence history and generation counter.
- Confirms that evidence from an older generation is rejected without changing the current dispatch state.
- Confirms that an unresolved `UNKNOWN` command remains blocked across restart until explicit evidence is provided.

## Safety boundary

These are regression tests for the local SQLite state machine. They do not authenticate evidence, guarantee atomicity with external physical actions, or certify TrainOS for safety-critical deployment.
