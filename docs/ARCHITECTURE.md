# Architecture and trust boundaries — Security v0.1.0

## Systems of record

- TrainOS: orchestration and 24 functional areas; **not** independent security authority.
- Security: policy decision, admission and evidence semantics; here only local simulation.
- Future broker: authenticated cross-UID peer credentials + OS MAC label verified at entry.
- Future witness: independently owned monotonic root, isolated key custody, CAS interface.
- Future permit authority: durable one-use permits and crash-consistent commit protocol.
- Future supervisor: independent lifecycle authority, not same-UID process watchdog alone.
- Each physical subsystem: separate local safety interlocks; Security cannot replace them.

## SP-IC-004 local data flow

`request (strict parse) → simulated broker principal match → versioned exact-match policy`
`→ BEGIN IMMEDIATE → verify complete local HMAC chain + live tip → unique request insert`
`→ SQLite commit → non-executable reference decision (ALLOW or DENY)`

The simulation can return `ALLOW` for **read/observe/simulate-only fixture operations**;
it is never a permit and cannot authorize hardware or production IPC.

## Production admission

`LocalSimulation.require_production_admission()` always raises `ProductionBlocked`.
Any operational service must refuse startup/actuation until independent systems prove
its complete set of required protections. A configurable boolean, fake witness, local
file, process environment or signed payload from the same UID is not such proof.

## Crash limits

SQLite FULL synchronous + WAL and BEGIN IMMEDIATE provide local transaction semantics;
they do not form a multi-store CAS or two-phase recovery protocol. A stolen HMAC key,
rollback of the *entire* SQLite database, or compromised same-UID process can forge a
plausible chain. In-memory `_last_tip` detects only a rollback while the process survives.
After service restart it cannot distinguish an authentic genesis from a full rollback.
Security must remain NO-GO until durable independent root verification closes this gap.

## Integration

Existing contracts `SP-IC-001..` and six module probes remain unchanged in meaning.
New optional `SP-SAFE` probe uses the same observation envelope with
`operationalReady=false` and `stageId=SECURITY-v0.1.0`. Neither the probe nor dashboard
can modify service permissions or deploy MAC profiles.
