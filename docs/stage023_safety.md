# ISLAND-GEO-022 — Safety engineering disposition

**Overall production decision: BLOCKED/NO-GO.** This Stage is an experimental research/protocol implementation, not a secure monotonic witness suitable for real assets, physical earthworks, tunnelling, or infrastructure operations.

## Threat and trust boundaries

The protected subject is admission of signed engineering measurements into an immutable(-intent) evidence ledger. A malicious same-UID broker process can still open the broker's private SQLite and import historic library APIs. UID DAC alone cannot distinguish it from the authorized broker. The root test orchestrator and host administrator can impersonate any of the six role UIDs; a software SQLite root and its signing key can both be rolled back. The independently trusted monotonic resource and MAC policy are explicitly missing.

| Hazard | Trigger | Current control | Remaining severity / disposition |
|---|---|---|---|
| H-GEO-022-01 | Simultaneous rollback of local, witness, permit and software root | No provable protection; explicit NO-GO | Critical / OPEN |
| H-GEO-022-02 | Forged/replayed root head | Fresh signed nonce challenge and pinned Ed25519 public key | Critical if key or signing service compromised / OPEN |
| H-GEO-022-03 | SIGKILL between witness and root CAS | Fail closed on divergent heads, no automatic repair | Critical availability impact; independent recovery procedure needed / OPEN |
| H-GEO-022-04 | Permit replay or stolen token | State-bound one-use tokens, distinct authority UID and kernel peer credentials | Critical if root/authority/host compromised / OPEN |
| H-GEO-022-05 | Legacy Python entrypoint under broker UID | MAC policy required; strict broker NO-GO | Critical / OPEN |
| H-GEO-022-06 | LSM label appears but policy does not cover same-UID code | Observe LSM, reject unverified policy | Critical / OPEN |
| H-GEO-022-07 | Unmanaged crash restart creates stale IPC, consumes token twice | Exclusive lock + fail-closed; no independent supervisor | Critical / OPEN |
| H-GEO-022-08 | Privileged adversary substitutes SQLite, keys, journal, lock, socket | Negative selected tamper tests and SO_PEERCRED; root attack not excluded | Critical / OPEN |
| H-GEO-022-09 | Host power loss between fsync operations | No certified fault hardware; `synchronous=FULL` does not prove media durability | Critical / OPEN |
| H-GEO-022-10 | Geotechnical admission mistaken for construction approval | Mandatory `engineering_approval=BLOCKED/NO-GO`, independent site design evidence absent | Catastrophic potential / OPEN |

## Crash consistency

A witness CAS and remote root CAS cannot be made atomic by two SQLite commits. This Stage deliberately blocks on mismatch instead of modifying the root automatically. A root that advances but witness fails likewise requires a trusted offline reconciliation protocol. Even a successful userland SIGKILL matrix is not a storage-power-loss experiment. Request nonce burn before CAS can permanently consume client requests without committing, so callers must obtain a fresh signed request and independent recovery authorization rather than retry the same nonce.

## Conditions to accept production security

Independent engineering and security assessment must show: actual root monotonic attestation with anti-rollback proofs outside mutable root/witness storage; loaded OS MAC/LSM policy preventing arbitrary legacy code under broker UID (including same-UID execution and service restart); independently verified service-manager pre-exec admission, cgroup/lifecycle control and restart; physically independent signing-key provisioning/rotation; recovery permit anti-replay and crash protection; end-to-end cross-UID adversarial verification including all witness/permit/root transaction boundaries; power-cut and storage rollback tests; and geotechnical field and regulatory reviews. None are inferred from this software regression.

**Physical construction & operations: BLOCKED/NO-GO.**
