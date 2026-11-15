# RAIL-TRUST-009 — Mandatory Lifecycle Lock Consolidation & Fault-Injection Closure

Status: PARTIAL / production BLOCKED / physical NO-GO.

## Requirements
- RT009-01: startup, socket teardown, IPC admission and offline recovery serialize through `admission.lock`.
- RT009-02: IPC admission retains the lifecycle lock across the admission transaction and does not recursively acquire `flock`.
- RT009-03: an unprovisioned independent anchor always fails closed.
- RT009-04: PREPARED state fences new admissions.
- RT009-05: a foreign peer UID cannot request admission.
- RT009-06: do not infer hardware/physical authorization from software release PASS.

## Contracts and implementation
`unified_admission.admit(..., _lock_held=False)` is backward-compatible. The private `_lock_held=True` option is ONLY for a caller already holding `anchored_admission._locked(directory)`; misuse outside this invariant is unsafe. `ProductionBoundary.handle_one()` now retains that lock during its call to `admit()`.

`ProductionBoundary.start()` and `.close()` use the same lock. `unified_admission.recover()` uses the same lock. A remote provider must independently guarantee monotonic durability and client authentication; the package does not provision one.

## Fault injection / negative evidence
- A real child process holding `flock` is SIGKILLed and the lock can be reacquired.
- A mismatched UID is rejected using a mocked peer-credential accessor (not a cross-UID E2E test).
- PREPARED blocks admission.
- Missing external provider blocks startup.
- IPC admission with malformed attestation returns BLOCKED without nested-lock deadlock.

## Safety and remaining gaps
- No exhaustive SIGKILL matrix across all SQLite/anchor/IPC critical points.
- No privileged broker or actual cross-UID recovery test.
- No independent hardware-backed or remote monotonic anchor provisioned.
- No proof against combined SQLite + filesystem rollback, privileged path replacement, or socket substitution during all transitions.
- Legacy direct library `release_gate.evaluate()` remains callable; library compatibility intentionally preserved, so all production bypasses are NOT proven eliminated.
- No hardware-in-loop, supervisory integration, physical train actuation, or independent safety assessment.

**Safety decision: BLOCKED / NO-GO.** This is a local software prototype, not a production safety assurance case.
