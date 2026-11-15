# ENERGY-CORE-018 — OS-Enforced Production Privilege Separation & Crash-Point Matrix

## Scope and requirements
- ENERGY-018-R1: opt-in production service must reject root, same UID witness/client, UID mismatches, unsafe protected paths.
- ENERGY-018-R2: preserve all legacy library APIs; they are NOT authorized production entry points.
- ENERGY-018-R3: reject symlink, unsafe owner/mode, and unprotected directory ancestors.
- ENERGY-018-R4: do not claim independent witness or full physical deployment safety without external evidence.

## Contract
`ProductionUIDPolicy(service_uid, witness_uid, client_uids).validate()` rejects invalid identity configuration.
`require_private_tree(paths, uid)` checks existing protected leaves and directory ancestry.
`IsolatedProductionEnergyService` extends attested service and checks the OS identity and protected directories before constructing the IPC endpoint. The caller must provision independent witness and actual OS permissions.

## Safety analysis and limitations
- DAC cannot constrain root or a malicious same-UID process. This is not a mandatory access control mechanism.
- Checking filesystem paths is subject to TOCTOU; no openat2/dirfd-based complete enforcement is claimed.
- SQLite DB, journal, checkpoint, phase and lock file ownership are not comprehensively verified at every access.
- A client can still import legacy modules; only a separately provisioned service UID with protected filesystem permissions can prevent writes to production files.
- Independent witness, cryptographic key custody and witness CAS atomicity remain external obligations.
- No exhaustive SIGKILL matrix was run; prior tests include limited crash simulation.
- A real cross-UID OS permission check was run when root/runuser were available, but not full service-to-service IPC with independently administered UIDs.
- Regression delays/hangs were previously observed in CORE-017 and may persist. Evidence must preserve interrupted runs.

## Evidence
`tests/test_stage018.py` includes policy rejection, private directory and symlink checks, and a real subprocess UID access denial when permitted. Full regression logs under `evidence/ENERGY-CORE-018-regression-*.txt`.

## Readiness
BLOCKED / NO-GO. No physical energy-system control is authorized.
