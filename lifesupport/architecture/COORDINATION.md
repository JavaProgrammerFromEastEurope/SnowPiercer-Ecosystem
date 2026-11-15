# LIFE-CORE-006 — Recovery Coordination & Integrity Fencing

## Scope
Offline logical-state SQLite coordination for cooperating processes sharing one SQLite database on a filesystem with correct SQLite locking semantics. This is **not** distributed consensus, hardware fencing, or a safety-certified controller.

## Algorithm
`FencedLifecycle` extends `PersistentLifecycle` without changing prior files. It persists a singleton `(epoch, owner, expires_at_ns, registry_fingerprint)` record in the same database as the event journal. `acquire` uses `BEGIN IMMEDIATE` and refuses to preempt an unexpired lease. On expiry or release, the next owner obtains an incremented epoch. `renew` updates expiry, invalidating the old token. A transition replays the journal, checks token, inserts the event, rechecks expiry, and commits in one SQLite write transaction. Failed checks roll back.

## Trust assumptions
All writers must opt into `FencedLifecycle`. **Legacy `PersistentLifecycle.transition` can still write to the same database**, a deliberately tested compatibility gap. An untrusted client with database write access can alter the coordination table. The wall clock must not jump backward; cross-host clock synchronization is not guaranteed. `time.time_ns()` is not a trusted monotonic shared clock. SQLite locks must function correctly. Expiry is not hardware shutdown. An epoch token is not cryptographically authenticated.

## Recovery and operations
Read-only inspection may use legacy APIs; do not deploy mixed writers. A fenced instance must acquire a token before `recover` or `transition`. Explicit release expires the lease. Crashed owners require lease expiry. Before any safety-critical deployment, enforce fencing at a single mandatory storage boundary, use trusted coordination/time and independently verified physical safety interlocks.

## Compatibility
All previous source files and tests retained. New module is opt-in; old API signatures unchanged. Database gains a `coordination` table only when opened with the new class. Backup/restore routines from LIFE-CORE-005 are not integrated into fencing and must not be treated as coordinated snapshots.
