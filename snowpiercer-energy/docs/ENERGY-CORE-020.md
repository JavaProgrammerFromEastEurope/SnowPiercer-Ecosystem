# ENERGY-CORE-020 — Mandatory Production IPC Admission & Exhaustive Cross-UID Crash Verification

## Status
Experimental partial implementation; production BLOCKED; physical NO-GO.

## Requirements and contract
- R20-01: opt-in service must require OS-separated service/witness/client UID policy and the existing witness verifier. `BoundedIsolatedEnergyService` inherits `IsolatedProductionEnergyService` and does not weaken its startup checks.
- R20-02: UNIX socket accepts must have bounded wait; request framing must be bounded by monotonic deadline and MAX_REQUEST.
- R20-03: authenticate client using kernel SO_PEERCRED, never client JSON.
- R20-04: dispatch each accepted request at most once; never retry on response disconnect.
- R20-05: preserve all legacy library exports, but do NOT represent legacy direct writes as production-authorized.
- R20-06: independent witness and independently protected storage are deployment prerequisites.

## Architecture
`BoundedIsolatedEnergyService` (production_ipc_v4.py) extends `IsolatedProductionEnergyService` -> `AttestedProductionEnergyService` -> `EvidenceReconciledEnergyService` -> `JournaledWitnessEnergyService`. It delegates UID authentication and bounded accept to `ipc_diagnostics.py` and dispatch to the pre-existing integrated service.

## Safety analysis
- Monotonic deadline applies to request receipt; it cannot forcibly interrupt synchronous SQLite, file locks, witness CAS or Python callback execution. Full transaction boundedness is NOT proven.
- Existing advisory lock is cooperative. Same-UID or privileged legacy calls can bypass it; global mandatory fencing NOT proven.
- Linux SO_PEERCRED authenticates the peer process; this does not establish independent witness or secure process provisioning.
- SQLite commit, phase journal, witness CAS and IPC delivery are not one atomic transaction. A crash can leave a pending phase that requires independent reconciliation.
- Rollback to genesis, substitution of DB/checkpoint/lock/socket, multi-UID end-to-end, SIGKILL at every boundary and full deadlock elimination remain BLOCKED until dedicated independent evidence is available.

## Evidence
- Four targeted tests `tests/test_production_ipc_v4.py` passed.
- Full suite regression logs are in `evidence/ENERGY-CORE-020-regression-*.txt`. Interrupted or failed runs must not count as PASS.
- Environment has Linux SO_PEERCRED support; this alone is not a full cross-UID production deployment.

## Decision
BLOCKED / NO-GO for production physical energy actuation. Simulation-only experimental capability.
