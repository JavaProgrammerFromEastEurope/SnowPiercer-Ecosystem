# ENERGY-CORE-015 — Witness Transaction Protocol & Cross-UID Production Enforcement

Version: 0.15.0. Status: EXPERIMENTAL / SAFETY BLOCKED / PHYSICAL NO-GO.

## Requirements and contracts
- WT-01: write and fsync an exclusive, owner-only phase intent before local ledger/permit mutation.
- WT-02: publish witness revision with compare-and-swap only after local mutation.
- WT-03: remove phase journal and fsync directory only after witness CAS succeeds.
- WT-04: startup rejects any pending or unsafe phase journal, including symlinks.
- WT-05: never auto-replay ambiguous transactions or reissue permits.
- WT-06: preserve existing API and test suite; add opt-in JournaledWitnessEnergyService.

## Architecture
`JournaledWitnessEnergyService` subclasses `WitnessedEnergyService`. It uses the existing checkpoint lock for local permit mutations and an O_EXCL phase journal to prevent overlapping cooperative journal transactions. The phase journal is stored in the owner-only checkpoint directory. A real independent witness is supplied by the deployment, not this library.

## Transaction and failure matrix
1. BEFORE phase create: no transaction initiated; safe to retry.
2. DURING phase fsync: partial or ambiguous journal may remain; fail closed.
3. AFTER phase fsync, BEFORE local SQLite commit: journal remains; fail closed.
4. AFTER local SQLite commit, BEFORE checkpoint/witness CAS: journal remains; fail closed.
5. AFTER witness CAS, BEFORE journal unlink: journal remains; fail closed.
6. AFTER journal unlink, BEFORE directory fsync: recovery depends on filesystem durability; not independently proven.
7. IPC disconnect after commit: no automatic replay; client must query verified state.

No automatic reconcile implementation is claimed. Operator-assisted independent evidence is required to clear an ambiguous journal. Deleting the journal without independent verification is unsafe.

## Safety limitations / open defects
- This is an opt-in simulation service. Legacy production IPC and direct library ledger APIs remain callable. Global mandatory production fencing is NOT implemented.
- No independently deployed witness, no externally administered monotonic root, and no proof of atomicity across local SQLite and remote witness CAS.
- No real cross-UID OS end-to-end tests, exhaustive SIGKILL matrix, or complete genesis rollback/substitution matrix. The existing test suite exercises narrower scenarios.
- Journal is local and same-UID writable. Privileged tampering or coordinated rollback is not defeated.
- A failed authorization after intent creation leaves a pending journal, deliberately requiring intervention (availability tradeoff).
- Concurrent startup, crash windows and privileged production isolation are not independently verified.
- The environment-dependent regression stall during second run was retained as evidence; its cause is not established.

## Evidence
- `tests/test_stage015.py`: five new tests for success, CAS failure, pending journal, symlink, replay.
- `evidence/ENERGY-CORE-015-regression-1.txt`, `-2-retry.txt`, `-3.txt`: three complete passing regressions, 158 tests each.
- `evidence/ENERGY-CORE-015-regression-2.txt`: interrupted partial run (not counted).
- `evidence/ENERGY-CORE-015-initial-failure.txt`: initial target test failure (documented).

Readiness: BLOCKED / NO-GO. No physical control or safety certification.
