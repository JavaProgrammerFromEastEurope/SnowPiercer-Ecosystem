# ENERGY-CORE-004 — Persistent Energy Ledger & Crash-Consistent State Recovery

## Scope / architecture
Simulation-only Python API `PersistentEnergyLedger(path, system)`; SQLite is the single durable commit authority. No IPC, physical actuation, or external checkpoint. `apply()` runs BEGIN IMMEDIATE, verifies full history, rejects replay/stale sequence, recomputes the accounting result against the last persisted storage state, inserts request/result/state/hash in one transaction, commits. `snapshot()` verifies full history and returns `(sequence, digest, storage_state)`.

## Requirements and contracts
- E004-R01: persist operation ID, request, deterministic accounting result and storage state in a single transaction.
- E004-R02: unique operation IDs must be rejected on replay, even for identical payloads.
- E004-R03: expected_sequence mismatch must be rejected; concurrent writers serialize via SQLite locks.
- E004-R04: on startup and before each operation, verify metadata, sequence continuity, hash chain and replayed accounting/state.
- E004-R05: crash before commit must leave no operation; crash after commit must leave one operation.
- E004-R06: all prior public library exports and tests must remain functional.
- E004-R07: simulation only, NO-GO for hardware deployment.

`apply(operation_id, requests, duration_h=..., dispatch=(), reserve_kw=0, expected_sequence=None, fault_hook=None)` returns `CommittedEnergy`. `fault_hook` is testing-only and is invoked at after_begin, after_verify, after_insert, after_commit. `snapshot()` returns current sequence, digest and storage state. A successful commit changes only the SQLite representation; the supplied `EnergySystem` is not mutated. `LedgerConflict` is a rejected replay or stale sequence; `LedgerIntegrityError` is detected integrity failure. Underlying SQLite I/O errors may propagate as sqlite3 exceptions and are not automatically classified.

## Safety analysis
- Crash mid-transaction: SQLite atomicity protects the row and state together on tested local environment; process-kill tests verify pre/post commit boundaries.
- Concurrent processes: SQLite `BEGIN IMMEDIATE` serializes writers; tested with distinct and duplicate operation IDs.
- Tampering: digest mismatch, missing middle entry and configuration mismatch detected. SHA-256 is **not authenticated**; an attacker with write access can rewrite the entire history and hashes.
- Rollback/truncation: deleting the last entries or replacing the entire database with an earlier valid copy is **not detectable** without an independent trusted monotonic anchor. No such anchor exists in this Stage.
- Filesystem: symlink/path substitution, UID isolation, permissions, fsync/power-cut durability, NFS/network filesystems, disk-full and malicious SQLite files have not been independently qualified.
- SQLite connection: process-local connections are opened per operation and explicitly closed. SQLite transaction lock is not a production admission lock for all legacy APIs.
- Storage accounting: floats, simplified efficiencies and static nominal generation; not calibrated physical measurements.
- Legacy `account()` and `simulate_allocation()` remain callable without ledger admission. No mandatory production gateway exists.
- Fault hook after commit may raise/kill after durable success, making client acknowledgement ambiguous; retry with same ID is rejected rather than replayed.

## Evidence and acceptance
Three full test suite runs with `-W error::ResourceWarning -W error::DeprecationWarning`, third-party pytest autoload disabled. Bounded enumeration and four SIGKILL points; not exhaustive of SQLite internals. Results in `evidence/energy-core-004-regression-{1,2,3}.txt`.

## Readiness
Software simulation acceptance: PASS for tested scenarios. Independent physical end-to-end acceptance: NOT PERFORMED. Physical deployment: **NO-GO**.
