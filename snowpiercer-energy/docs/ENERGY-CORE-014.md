# ENERGY-CORE-014 — Independent Trust Root & Mandatory Production Isolation

## Requirements and contracts
- R014-01: Optional external witness must be supplied explicitly; absent/unreachable witness rejects startup.
- R014-02: WitnessRecord binds revision, ledger sequence/digest, permit database fingerprint.
- R014-03: Witness compare_and_swap must be durable, monotonic and independently administered. This is an **interface contract**, not an implementation of a trusted witness.
- R014-04: Detect local permit DB + checkpoint coordinated rollback when external witness has not rolled back.
- R014-05: Reject stale or unavailable witness and rejected CAS. No automatic reconciliation or rollback of permits.
- R014-06: Legacy library APIs retained for compatibility. They are **not** fenced at the OS boundary. Production isolation is **BLOCKED**.

## Architecture
`WitnessedEnergyService -> AnchoredDurableEnergyService -> DurableEnergyService -> IntegratedEnergyService -> UnifiedEnergyAdmission -> TrustedEnergyGateway`.
External witness has `read() -> WitnessRecord` and `compare_and_swap(expected, updated) -> bool`. A deployment must separately attest witness durability, access controls, monotonicity and independent administration.

## Crash consistency and safety
SQLite permit consumption and witness CAS are not a distributed transaction. If a crash occurs between local commit and witness update, subsequent operations reject divergence (fail closed), but operator intervention is needed. An attacker who can roll back both local state and the witness defeats detection. Concurrency across processes is not linearizable because witness verification and local mutation are not protected by a shared external lock; CAS rejects one contender after local mutation, leaving divergence and requiring intervention. Legacy IPC and direct ledger API remain callable. `ENERGY_TEST_CRASH_POINT` remains a test-only injection point in inherited code.

## Evidence
- New tests: `tests/test_stage014.py`: 5 passed.
- Full regression logs: `evidence/ENERGY-CORE-014-regression-{1,2,3}.txt`: each 153 passed, warnings treated as errors.
- An intermediate attempt at second run was interrupted by execution timeout; final rerun passed. Not evidence of a deterministic product failure.
- No independent witness deployed. No real different-UID end-to-end tests, exhaustive SIGKILL matrix, full ledger-to-genesis rollback test, or complete file/socket substitution matrix performed in this Stage.

## Safety decision
**BLOCKED / NO-GO** for physical systems and production admission. No independent end-to-end security claim.
