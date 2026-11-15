# ENERGY-CORE-016 — Witness Reconciliation & Mandatory Production Admission Enforcement

Status: **PARTIAL / BLOCKED / PHYSICAL NO-GO**. Simulation only.

## Requirements and contracts
- R16-01: Pending witness phases remain fail-closed on service startup. **PASS** (inherited).
- R16-02: Reconciliation must require a caller-provided external evidence verifier. **PASS** in unit tests; verifier independence unproven.
- R16-03: Evidence binds phase action, pre-transaction witness record, and current witness record. **PASS**.
- R16-04: Clear phase only if witness revision advances by exactly one, local ledger and permits match witness, and verifier explicitly returns `True`. **PASS** in test harness.
- R16-05: Never automatically replay transactions, modify SQLite, or advance witness during reconciliation. **PASS** by implementation inspection.
- R16-06: Production entry-point fencing across legacy APIs. **BLOCKED**: legacy constructors and direct ledger writes remain available.
- R16-07: Real cross-UID tests. **BLOCKED**: no verified privileged multi-UID fixture.
- R16-08: Exhaustive SIGKILL matrix across SQLite, phase, witness, IPC. **BLOCKED**.
- R16-09: Independent witness and verifier with durable monotonic CAS. **BLOCKED**: injected interfaces only.

## Architecture
`EvidenceReconciledEnergyService` extends `JournaledWitnessEnergyService`. It reads `witness.phase` with O_NOFOLLOW, checks inode owner/mode/link count and bounded size, binds the phase to `ReconciliationEvidence`, validates witness and local fingerprints, requires a positive external verifier decision, checks state again, and only then unlinks the phase and fsyncs the directory. It never modifies ledger, permits, or witness.

## Safety analysis
- Threat: false external evidence / compromised verifier. Mitigation: verifier is mandatory, but its independence is a **deployment obligation**; no guarantee against compromised verifier.
- Threat: local rollback or witness disagreement. Mitigation: phase remains and operation fails closed for detectable mismatch.
- Threat: full rollback to genesis including witness. **Not mitigated** without independent monotonic root.
- Threat: legacy production bypass. **Not mitigated**; legacy APIs remain callable to preserve library compatibility. Must enforce OS-level isolation and privileged production entry point externally.
- Threat: cross-process TOCTOU. The implementation uses existing advisory locks but lacks a separately verified end-to-end multi-process isolation proof.
- Threat: crash after witness CAS and before phase removal. Explicit evidence-gated reconciliation can clear an already completed phase, without replay. Crash during phase removal may require repeated operator verification.
- Threat: concurrent external witness changes. Re-read before clear; this is not a substitute for externally guaranteed CAS semantics.

## Evidence
New `tests/test_stage016.py` covers successful approved cleanup, rejected verifier, stale witness, mismatched pre-state and local semantic mutation. Four successful full strict regression logs: runs 1, 2, 3, 4 (163 tests each). One earlier orchestration command timed out while awaiting completion, but the saved run-3 log confirms its full success. The initial focused run emitted a PytestUnraisableExceptionWarning from a test-created unclosed sqlite3 connection; the test was fixed before full regressions. No real cross-UID execution or exhaustive SIGKILL campaign is claimed.

## Decision
**BLOCKED / NO-GO** for production and physical energy systems. Independent end-to-end witness, cross-UID, crash-point and mandatory admission guarantees remain unproven.
