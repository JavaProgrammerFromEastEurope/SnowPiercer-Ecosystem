# RAIL-TRUST-002 — Mandatory Trusted Admission & Atomic Replay-State Recovery

## Requirements and contracts
- RAIL-TRUST-002-R1: Production release CLI MUST reject missing signed baseline, independent trust store or persistent state database.
- R2: An Ed25519 attestation MUST match the current source manifest and trusted, non-revoked key.
- R3: Sequence and nonce MUST be consumed only after local software release checks pass.
- R4: Concurrent admission MUST serialize with SQLite `BEGIN IMMEDIATE`; transaction rollback MUST leave state unchanged on abrupt termination before COMMIT.
- R5: Legacy library APIs remain import-compatible but MUST NOT be treated as production release authorization.
- R6: State and trust files require trusted deployment and protected ownership/permissions.

`assess_admission(root, baseline, attestation, trust, db_path)` returns PASS, FAIL or BLOCKED. `admit` raises on failures. `python -m railsystem.release_cli --baseline ... --attestation ... --trust ... --state-db ... --output ...` is the supported production software release entrypoint. `trust_cli` delegates to it. The legacy `release_gate.evaluate()` and `trust.evaluate_trusted()` are retained as non-production library helpers.

## Crash model and safety analysis
SQLite uses DELETE journal, synchronous FULL, `BEGIN IMMEDIATE`, and one transaction covering replay state read, signature verification, local test gate and state update. A process terminated before COMMIT should leave replay state unchanged; concurrent admissions to one DB serialize. Post-COMMIT results can be lost to the caller: retry is rejected as replay (conservative ambiguity). SIGKILL cannot be caught; tests use process exit inside transaction to emulate abrupt termination. Production filesystem durability, directory fsync, power loss, network filesystems and storage controller behavior are not validated.

Hazards: unauthorized release on trust bypass, replay after DB rollback, trust root substitution, DB replacement, compromised UID, and loss of availability under long-held locks. Controls: strict production CLI, Ed25519 verification, nonce and monotonic sequence checks, protected file preflight, transactional SQLite. Residual risks: no independent anti-rollback anchor; privileged attackers can replace both trust and DB, and symlink/TOCTOU attacks against DB path remain possible between preflight and sqlite open. Filesystem ACLs and multi-UID deployment require independent review. Source manifest does not hash the release CLI packaging/entrypoint outside registered paths. This stage is NOT train-control safety certification.

## Evidence and release decision
Tests cover normal admission, replay, rollback, key revocation, tampering, protected file checks, CLI blocking, process concurrency and simulated crash. Release authorization for real systems remains BLOCKED/NO-GO pending independent provisioning, end-to-end integration and operational safety validation.
