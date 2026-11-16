# TrainOS Stage 83 — Direct Event Store Read Guard

## Changes
- Audited kernel consumers of `CommandEventStore`: diagnostic evidence collection reads through `EventRegistry`; the registry already gated its read APIs when configured.
- Added opt-in `CommandEventStore.enable_trusted_reads(anchor_store)` so direct `get_events()` and `all_events()` calls also require a fresh `EventLogRecoveryGate` assessment.
- Enabling the guard rejects an anchor store configured with the same database path.
- `EventRegistry(require_trusted_reads=True, ...)` configures the underlying store guard, so callers cannot bypass the guard merely by retaining a reference to that store.
- Legacy behavior remains unchanged unless trusted reads are explicitly enabled.

## Validation
- Stage 83 tests cover absent anchors, verified reads, payload tampering, registry-to-store integration, and same-path rejection.

## Limitations
- This is opt-in application-layer protection; raw SQLite access and internal integrity metadata methods remain available to code with direct object/database access.
- Separate local SQLite files are not equivalent to remote immutable storage. The anchor DB and signing keys need independently controlled access for stronger guarantees.
- Not a safety-certified railway control mechanism.
