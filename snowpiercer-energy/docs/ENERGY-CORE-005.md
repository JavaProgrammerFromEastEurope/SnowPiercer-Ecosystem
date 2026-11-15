# ENERGY-CORE-005 — Trusted Ledger Anchoring & Mandatory Admission Control

Version: 0.5.0; safety decision: BLOCKED / NO-GO for production and hardware.

## Requirements and contracts
- REQ-005-01: Retain all public CORE-001 through CORE-004 APIs; additive trust module only.
- REQ-005-02: Simulated writes submitted to `ProductionEnergyAdmission.submit_simulation` must pass `TrustedEnergyGateway` and its interprocess `flock`.
- REQ-005-03: Write a durable pending anchor before SQLite commit; finalize only after commit.
- REQ-005-04: On restart reconcile only exact previous head or exact pending successor; otherwise fail closed.
- REQ-005-05: Reject reused operation IDs and stale sequence numbers.
- REQ-005-06: Detect unguarded SQLite mutation and independently rolled-back SQLite file when anchor remains intact.
- REQ-005-07: Reject hardware commands and legacy writes submitted to the production admission facade.
- REQ-005-08: Exercise subprocess SIGKILL and concurrent writers; run 3 full regressions with warning categories treated as errors.

## Architecture
`ProductionEnergyAdmission -> TrustedEnergyGateway -> PersistentEnergyLedger -> SQLite`.
The gateway stores `energy.anchor` and `energy.lock` in a separately configured local directory. The lock serializes participating processes only. Anchor uses temp-file, fsync, atomic rename and directory fsync. Ledger retains SQLite DELETE journaling with synchronous FULL.

## Recovery contract
Committed anchor (N,H), optional pending (N+1,H'). If SQLite head equals committed, clear pending; if equals pending, finalize pending; otherwise refuse. An absent anchor is initialized only for an empty ledger during construction. An absent anchor on later access fails closed. All paths remain simulation-only.

## Safety analysis
- SQLite rollback alone: detectable if anchor is preserved.
- SIGKILL before/after SQLite commit: recoverable under tested filesystem/process conditions.
- Same-UID attacker modifying both anchor and DB: NOT PROTECTED.
- Removing anchor and reverting database to empty genesis: NOT PROTECTED; bootstrap is not externally authenticated.
- Malicious directory replacement, privileged adversary, filesystem crash, NFS lock behavior, power loss: NOT VERIFIED.
- Legacy `PersistentEnergyLedger.apply` remains directly callable for compatibility: mandatory global admission NOT ENFORCED; detected on next gateway check, not prevented.
- SQLite and external anchor are not a single atomic transaction; pending recovery relies on durable ordering and cooperative writers.
- Physical protection, hardware actuators, authenticating IPC callers and independent root of trust: NOT IMPLEMENTED.

## Evidence
See `evidence/energy-core-005-regression-{1,2,3}.txt`. Tests cover basic admission, rollback, tampering, legacy bypass detection, missing anchor, recovery, 4 SIGKILL boundaries, multiprocessing and symlink directory. `pytest` third-party plugin autoload disabled. Unit tests are not independent end-to-end certification.

## Decision
BLOCKED / NO-GO for production and physical energy operation. Do not claim trusted anti-rollback against a malicious filesystem administrator.
