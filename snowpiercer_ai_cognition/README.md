# SnowPiercer AI / Cognition

Stages: AI-CORE-001 Cognitive Foundation & Safe Decision Interface; AI-CORE-002 Trusted Observation Admission & Replay Protection.

Python 3.9+ standard library only. `assess()` remains the legacy pure deterministic recommendation API. For authenticated admission use `ReplayStore`, `TrustedAdmission`, `signed_envelope`; see `docs/CONTRACT.md`. No direct actuation.

Run complete available AI / Cognition regression:

```bash
PYTHONPATH=. python -W error::ResourceWarning -m unittest discover -s tests -v
```

This suite does **not** execute TrainOS v80 tests or cross-subsystem integration tests. Stage 002 remains NO-GO for safety-critical operation.

## AI-CORE-003 — Trusted Key Lifecycle & Crash-Consistent Replay Recovery
Adds `RotationManager`, persistent rotation phases, explicit bootstrap and recovery, independent epoch file checks, and mandatory legacy replay reservation fencing. Python 3.9+; no third-party dependencies. Example: create `ReplayStore(path)`; construct `RotationManager(store,anchor,{'trainos':key},bootstrap=True)` on a new empty database; call `provision('trainos')`, then `admit(envelope,clock=...)`; rotate with `rotate('trainos',new_key)`. Never use bootstrap with a restored database. This implementation is a demonstrator, not certified safety control.

Run regression: `python -W error::ResourceWarning -m unittest discover -s tests -v`.

## AI-CORE-004 — Independent Trust Anchoring & Recovery Authorization Hardening
Added opt-in `IndependentAnchor` and `HardenedRotationManager` with authenticated checkpoints, HMAC-bound single-use recovery tokens, lifecycle audit events and legacy key fingerprint checking. Existing interfaces retained. See `docs/SAFETY.md` for open bypass and rollback risks; no safety-critical deployment approval.
Run `python -W error::ResourceWarning -m unittest discover -s tests -v` from project directory.

## AI-CORE-005 — Mandatory Admission Gateway & Transactional Trust Enforcement
Use `MandatoryAdmissionGateway` with an existing `HardenedRotationManager` and an independently provisioned 32-byte audit secret. Enrol once with `bootstrap=True`, then reopen with `bootstrap=False`. New `gateway.admit(envelope)` checks source authentication, time window, rotation state, independent anchor and HMAC audit chain; it commits replay reservation and audit record atomically. Enrolled databases reject ordinary direct legacy inserts through SQLite triggers. This is a software protection boundary, not privileged filesystem isolation or hardware trust. See `docs/SAFETY.md`.

## AI-CORE-006 — Independent Audit Anchoring & Privileged Write Fencing
New `AuditCheckpoint` and `AnchoredAdmissionGateway` preserve prior public interfaces. The authenticated audit checkpoint detects truncation/rollback of the database audit tail when the checkpoint is retained in a separate protected failure domain. Crash after database commit fails closed and requires explicitly approved one-entry reconciliation. Ordinary separate-process SQLite inserts remain blocked by gateway triggers; privileged DDL or filesystem access can bypass them. OS-level privilege separation is NOT implemented. See `docs/SAFETY.md` for detailed limits.

Run: `PYTHONPATH=. python -W error::ResourceWarning -m unittest discover -s tests -v`

## AI-CORE-007 — OS-Enforced Admission Isolation & Cryptographic Recovery Authorization
`AdmissionIPCServer` exposes a bounded Unix-domain socket protocol (`admit`, `verify`, `recover`) with Linux `SO_PEERCRED` UID allowlists. `RecoveryAuthorizer` verifies checkpoint-bound HMAC permits and records consumed token IDs in SQLite. `ipc_request` is a minimal local client. Existing APIs remain unchanged. **Deployment must use a dedicated service UID**, restrictive socket directory and database/anchor/key ownership; tests in this archive do not assert that those OS controls have been deployed. One request is handled at a time, with bounded read timeout. Service is a prototype, not certified.

## AI-CORE-008 — Enforced Service Identity & Filesystem Access Isolation
`service_identity.py` provides strict filesystem preflight, provisioning for empty directories, and `IsolatedAdmissionIPCServer`, an opt-in wrapper requiring a non-root service UID and a private socket directory. Prior APIs are unchanged. For actual isolation, deploy with a dedicated UID distinct from clients, and provision private data directory `0700`, regular data/key/checkpoint files `0600`, and a socket directory `0700`. The socket mode remains `0600`: grant access only through a separately designed authorized mechanism (e.g., group policy or broker); changing it without threat review is unsafe. The existing IPC service remains available for legacy compatibility but does not automatically enforce the new preflight. The new wrapper must be selected explicitly. No production service manager or full SIGKILL restart orchestration is implemented.

### AI-CORE-009
Cross-UID IPC service (`ai_cognition.cross_uid`) with Linux filesystem layout verification and bounded child restart supervisor. The new entry point is opt-in; original APIs remain intact. See `docs/CONTRACT.md`, `docs/SAFETY.md` and `evidence/stage_validation_009.json`. End-to-end automatic gateway recovery after SIGKILL is not yet proven.

## AI-CORE-010 — End-to-End Crash Recovery & Mandatory Service Isolation Enforcement (partial)
Adds `ai_cognition.recovery_service` with guarded stale-socket reclamation and fail-closed startup checks. The production entrypoint guard is opt-in, not an enforced replacement of all legacy APIs. SIGKILL test validates Unix socket reclamation and rebinding; complete service restart with SQLite reinitialization and cross-UID resumed admission is not yet demonstrated. See `evidence/stage_validation_010.json` and `docs/SAFETY.md`.

## AI-CORE-011 — Mandatory Recovery Orchestration & Legacy Admission Fencing
`ai_cognition.orchestration.AdmissionSupervisor` provides finite-budget Linux process restarts, dedicated UID launch, socket-owner checks and `verify` readiness fencing. `production_admission(..., production=True)` rejects direct gateway registration while leaving library APIs unchanged. The actual service executable must construct a **new** SQLite/gateway/checkpoint instance after each restart and fail closed on drift. The supervisor never reconciles anchors. This Stage is a **partial implementation** of the requested end-to-end recovery: no integrated full anchored-gateway restart test and no universal prevention of direct legacy imports.

## AI-CORE-012 — End-to-End Anchored Recovery & Mandatory Production Admission Consolidation

New `ai_cognition.production012` supplies `ProductionAdmissionIPCServer`, `DurableRecoveryAuthorizer` and a trusted factory entrypoint (`python -m ai_cognition.production012 module:function`). Existing library APIs remain available. Production registration must use the new anchored IPC class; the legacy library API is not an OS-enforced prohibition. Each factory invocation constructs a fresh gateway and must verify its SQLite, key anchors and audit checkpoint before socket publication. The Stage does **not** implement a fully provisioned cross-UID production factory or demonstrate an end-to-end supervisor restart with live observation admission; these are open gaps.

Recovery is deliberately fail-closed: an unmatched SQLite audit head blocks admission. A cryptographically authenticated one-time permit is durably consumed in SQLite before the independent checkpoint advances. If killed in the gap, the permit cannot be reused; a new operator-approved permit is required. This is not an atomic SQLite/external-anchor transaction and is not a proof against a privileged attacker rolling back both stores. Avoid automatic reconciliation.

## AI-CORE-013 — Mandatory Production Runtime Isolation & Full-Chain Crash Recovery Verification
`ai_cognition.production013` adds a trusted, file-provisioned production process entrypoint. It rebuilds ReplayStore, HardenedRotationManager, AnchoredAdmissionGateway and ProductionAdmissionIPCServer on every launch. The service refuses root UID, untrusted config permissions, non-private files, unverified anchors and socket substitution. An authorized cross-UID client uses a group-accessible socket while the SQLite database remains private to the service UID. The supervisor now accepts an explicit service_gid to support this deployment.

**Run**: `python -m ai_cognition.production013 /private/config.json` after independent provisioning. The config is 0600 owned by the service UID, and contains sensitive keys; provision via secure channels, never through IPC. The private directory is 0700; IPC directory is 0710, owned by service UID and IPC group. Only a trusted administrator may select the service UID, group, executable, and config. The config must not be supplied by untrusted users.

The Linux root-only integration tests create separate service UID 65533 and client UID 65534. They verify successful cross-UID IPC, filesystem denial, actual SIGKILL/restart and new SQLite connection, replay persistence, tampered checkpoint fail-closed, socket substitution refusal, and supervisor restart. On hosts without root privileges these tests are skipped, not claimed as passed.

**Limits:** No hardware monotonic root of trust, no atomic SQLite/external-checkpoint commit, no prevention of a privileged administrator or arbitrary direct Python imports. A crash between SQLite COMMIT and checkpoint write remains fenced and requires an offline, separately authorized recovery workflow; the service will not publish a socket while fenced. No industrial systemd deployment, production certificates, or physical safety validation. The stage does not implement universal OS interception of legacy library APIs. Safety-critical readiness: NO-GO.

## AI-CORE-014 — Crash-Consistent Audit Recovery & Mandatory Production Write Fencing

Introduces `ai_cognition.production014.PhaseJournal` and `JournaledAdmissionGateway`. This is a **partial** Stage: the journal is crash-durable and detects pending phases; it is not yet wired into all production013 entry points. See `docs/REQUIREMENTS_014.md` for limitations and evidence.

## AI-CORE-015 — mandatory journaled production entrypoint (PARTIAL)

Use `ai_cognition.production015` with pre-provisioned `phase_journal` and `phase_key`.
New production IPC admissions pass through `JournaledAdmissionGateway`; recovery IPC is disabled.
Historical production entrypoints are still present for compatibility and MUST be disabled by deployment policy.
Cold crash recovery after DB commit and before checkpoint is not fully implemented; see `docs/REQUIREMENTS_015.md`.

### AI-CORE-016
Offline cold-recovery prototype: `ai_cognition.production016.cold_recover`; requires a stopped service, trusted operator, signed permit and PREPARED journal. Production entrypoint remains `python -m ai_cognition.production015 <config>`. Legacy `production012` CLI disabled. `production013` CLI is **not** yet fenced. Status PARTIAL / NO-GO.

### AI-CORE-017 (PARTIAL)
Legacy production013 executable disabled; previous library APIs retained.
Three focused tests passed. Full cumulative regression timed out and critical
crash-window recovery remains unverified. See evidence/stage_validation_017.json.

### AI-CORE-018 (PARTIAL / NO-GO)
Deterministic test-only SIGKILL injection across six crash points; cold recovery after checkpoint publication; rejected replay no longer poisons journal when state remains verified. Focused crash matrix passed; full cumulative regression remains unresolved. See docs/*_018.md and evidence/stage_validation_018.json.

### AI-CORE-019
Offline cold recovery now refuses concurrent recovery lock holders immediately and rechecks socket occupancy while holding the lock. New cross-process tests cover lock contention, invalid permits, and symlinked lock paths. Full regression logs and their completion status are stored in `evidence/`. The recovery lock is advisory and does not yet coordinate all production service startups. Safety-critical NO-GO.

### AI-CORE-020 (PARTIAL)
Introduces `locking020.py` shared local flock for official production015.run startup/serve and offline cold recovery. The standalone direct `create_service()` library API is retained and is not a production security boundary. New tests: `tests/test_locking020.py`. Full regression is not certified for this Stage.

### AI-CORE-021 — Context-bound TrainOS review proposals

Adds opt-in `TrainOSRecommendationBridge` with authenticated proposal provenance,
TrainOS context identity/revision/digest, bounded expiry and immutable read-only
results. A thread-safe process-local clock high-watermark prevents an expired
proposal from reviving after an observed wall-clock rollback in the same bridge.
The clock fence is not persistent across new instances or process restarts.
Existing trusted admission/replay and journal fencing remain in use.
The bridge never authorizes or executes a command. Production IPC is unchanged.
See `docs/STAGE_AI-CORE-021.md` for API, acceptance criteria and limitations.

Full unprivileged regression: 215 discovered, **147 passed, 68 skipped**, exit 0;
30 new tests. Root-only fixture checks run before privileged setup, fixing 8
non-root baseline errors. Skipped cross-UID/crash checks are not passed evidence.
Safety-critical readiness remains **NO-GO**. No external AI model was invoked.
