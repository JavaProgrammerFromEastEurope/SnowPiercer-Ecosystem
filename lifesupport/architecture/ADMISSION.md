# LIFE-CORE-007 — Mandatory Write Fencing & Recovery Admission

## Boundary
An explicit, opt-in migration installs SQLite event triggers. INSERT requires the `ls_admitted()` connection-local UDF to return 1. Only `AdmittedLifecycle.transition` registers this UDF and activates it while the inherited `FencedLifecycle.transition` validates the lease in the same SQLite write transaction, both before and after the append. UPDATE and DELETE are rejected.

## Migration
Open `AdmittedLifecycle`, acquire an unexpired fencing lease, then call `protect(token)`. This replays the journal and creates a schema version marker and three triggers transactionally. Repeating protect is idempotent. Existing events remain unchanged. Do not modify the database using out-of-band DDL.

## Compatibility
Unprotected legacy journals continue to work. Protected journals remain readable by `PersistentLifecycle`; legacy `transition` raises `sqlite3.OperationalError`. `FencedLifecycle` without admission UDF also cannot append to protected journals. Previous 93 tests pass unchanged.

## Known limitations
SQLite trigger DDL can be removed by any client with unrestricted database DDL privileges; file-system attackers can replace database files. A malicious client could register a counterfeit UDF. The current guard does not protect coordination and metadata tables, and does not provide cryptographic identity or remote consensus. Wall-clock leases are not a distributed safety guarantee. This is an offline logical lifecycle prototype; never connect it directly to safety-critical equipment.
