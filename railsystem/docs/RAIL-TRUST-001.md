# RAIL-TRUST-001 — Trusted Baselines & Cryptographic Attestations

## Requirements and contracts
- TRUST-001: Ed25519 signature MUST cover canonical JSON payload with domain, baseline ID, SHA-256 manifest digest, key ID, monotonic sequence, unique nonce.
- TRUST-002: Only independently provisioned, non-revoked public keys may approve a baseline.
- TRUST-003: Any source file mismatch, malformed signature, unknown key, or revoked key MUST fail closed.
- TRUST-004: Replay and rollback require externally persisted monotonic state; local caller MUST commit `proposed_next_state` atomically in an independently protected store before using PASS.
- TRUST-005: Missing inputs MUST produce BLOCKED; invalid supplied inputs MUST produce FAIL.
- TRUST-006: Legacy library APIs remain callable for compatibility, but MUST NOT be treated as production release authorization. Production integration MUST invoke `evaluate_trusted` or `trust_cli`.

## Trust boundary / safety analysis
Attestation authenticates a manifest only relative to an independently trusted public key. No private key is packaged. Key revocation and monotonic state are externally managed; a compromised trust store, rollback of external state, concurrent approvals, compromised signing key, filesystem races between hashing and execution, or self-reported regression evidence remain unresolved. `PASS` is a conditional *offline software gate result*, never permission for physical railway operations. The library does not commit state and therefore cannot guarantee single-use permits under concurrency. Integration must reject a PASS unless the next state has been durably committed by a trusted, serialized service. Legacy `release_gate.evaluate` is preserved for library compatibility and can still report PASS without a signature; production callers must not use it.

## Evidence
`tests/test_trust.py` covers signature validity, tampering, revocation, replay, rollback, manifest binding, strict gate integration and missing trust inputs. Full cumulative unittest results are recorded separately. No independent signer, HSM, cross-UID tests, or production TrainOS integration is claimed.
