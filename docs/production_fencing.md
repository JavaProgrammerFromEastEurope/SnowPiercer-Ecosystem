# ISLAND-GEO-010 — production fencing safety case (OPEN)

The hardened profile adds UID separation policy, connected-peer credential pinning, private-file checks, and lock inode checks. It is **opt-in** and therefore does not enforce production fencing across the complete codebase. The existing `AnchoredAdmission` API remains callable for compatibility. `HardenedProductionServer` selects `PinnedWitnessClient` for the inherited admission flow. This protects the connected witness peer UID but does not establish independent storage or mandatory fencing for legacy callers.

## Unverified boundaries
- Three independently provisioned operating-system UIDs and directory ACLs.
- Immutable external witness, rollback to genesis and replacement of witness database.
- Exhaustive SIGKILL injection across SQLite BEGIN/COMMIT, phase journal, witness CAS, IPC accept/reply.
- Multi-process races and cross-user filesystem tampering.
- TOCTOU races involving sockets, lockfiles, database and journals.
- Mandatory OS-enforced removal of legacy production write privileges.

## Decision
Production security: **BLOCKED/NO-GO**. Physical construction and operations: **BLOCKED/NO-GO**. Unit tests do not establish independent end-to-end guarantees.
