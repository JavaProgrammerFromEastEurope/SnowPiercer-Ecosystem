# ENERGY-CORE-017 — Mandatory Production Boundary & Independent Witness Attestation

Version: 0.17.0. Simulation-only; PHYSICAL NO-GO.

## Requirements and contracts

- R17-01: preserve legacy library API. Implement an opt-in production entry point that fails closed if the verifier is absent.
- R17-02: validate owner and restrictive permissions of the production socket directory and checkpoint directory.
- R17-03: accept only externally verified, issuer-bound attestation over canonical serialized reconciliation evidence.
- R17-04: never automatically clear ambiguous witness transactions; only reconcile previously completed, locally matching witness CAS with positive verification.
- R17-05: reject modified evidence, bad signatures, unrecognized issuers and missing verifiers.

## Architecture

`AttestedProductionEnergyService` extends `EvidenceReconciledEnergyService`. A caller-supplied `verifier(issuer, payload, signature)` must return the literal `True`; the implementation contains no production signing key. Evidence is encoded using sorted canonical JSON. `reconcile_completed` additionally verifies witness revision, local state, and pending phase before clearing.

## Threat model and safety analysis

The test verifier uses HMAC solely as a test fixture; it does not demonstrate independent trust, key isolation, or cryptographic strength of an actual deployed witness. The production boundary is opt-in: legacy modules and direct ledger API remain callable, so global mandatory production fencing is **BLOCKED**. Same-UID or privileged processes can bypass software policy and manipulate files. `flock` is advisory. A malicious owner can modify the verifier. Real different-UID end-to-end isolation, complete rollback-to-genesis protection, independent witness durability and exhaustive SIGKILL coverage are **NOT PROVEN**. Physical deployment: **NO-GO**.

## Evidence

Six new targeted tests cover attested reconcile, bad signature, bad issuer, modified evidence, unsafe directory and missing verifier. Full regressions: runs 1, 2 and 4 passed 169/169 with ResourceWarning, DeprecationWarning and PytestUnraisableExceptionWarning treated as errors. Earlier run 2 and run 3 attempts were interrupted by execution time limits; retain their logs and do not count them as PASS. Cross-UID processes and exhaustive crash-point matrix were not executed.

## Next

ENERGY-CORE-018 — OS-Enforced Production Privilege Separation & Crash-Point Matrix.
