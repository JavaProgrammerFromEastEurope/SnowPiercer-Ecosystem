# ENERGY-CORE-009 — Cross-UID Recovery Broker & Mandatory Legacy Production Fencing
Status: experimental PASS; production safety BLOCKED; physical NO-GO.

## Requirements / traceability
R01: Linux SO_PEERCRED authenticates UID: `recovery_broker.py:serve_one`, IPC tests.
R02: Single-use UID-bound random permits: `issue/recover`, replay and wrong-UID tests.
R03: Recovery verifies sequence and digest under unified advisory lock: stale-permit test.
R04: Socket inode and fork isolation: substitution and fork tests.
R05: Fail-closed on detectable ledger/anchor mismatch: missing-anchor and legacy-bypass tests.
R06: Global mandatory legacy production fencing: BLOCKED; legacy `PersistentEnergyLedger.apply` and `EnergyIPCServer` remain callable.
R07: Real different-UID E2E: BLOCKED, not exercised.
R08: Exhaustive SIGKILL across all new IPC/SQLite/anchor boundaries: BLOCKED; prior limited crash tests retained.
R09: Independent trust anchor: BLOCKED; local mutable anchor is not a trusted root.

## API / IPC contract
`CrossUIDRecoveryBroker(admission, socket_path, allowed_uids)` context manager and `serve_one()`; `broker_request(path, request)` client. Exact newline JSON requests: `{"action":"issue"}` or `{"action":"recover","token":"..."}`. UID comes only from kernel peer credentials. Permits are volatile and consumed on attempt; restart invalidates all. No physical commands.

## Architecture / safety analysis
Client -> SO_PEERCRED -> UID allowlist -> volatile permits -> unified advisory flock -> gateway -> SQLite + local anchor. Threats not mitigated: same-UID compromise, legacy direct writes, simultaneous DB/anchor rollback, filesystem tampering, process crash permit loss, denial of service, and unverified power-loss durability. All protection claims apply only to tested paths. No hardware admission.

## Verification
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -W error::ResourceWarning -W error::DeprecationWarning -m pytest -q` (three logs in evidence). No independent cross-UID E2E or exhaustive SIGKILL evidence. NO-GO.
