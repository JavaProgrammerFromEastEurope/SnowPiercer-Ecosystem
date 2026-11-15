# Safety analysis — AI-CORE-001

| Hazard | Mitigation | Residual risk |
|---|---|---|
| AI directly actuates safety-critical equipment | Pure function, actionable=false, no command interface | Downstream consumer could misuse recommendations |
| Malformed input accepted | Exact schema and bounded fields | Valid but malicious descriptions remain possible |
| Non-deterministic assessments | Fixed severity mapping and canonical evidence hash | Severity is supplied by caller and may be wrong |
| Forged / replayed observations | Not solved in Stage 001 | Requires authenticated provenance, anti-replay, trusted timestamps |
| Misleading AI capability claims | Explicit deterministic baseline designation | No model evaluation or operational certification |

Status: **NO-GO** for autonomous control, production safety use and physical actuation. Next stage should address authenticated admission, freshness, bounded processing and integration conformance.

# AI-CORE-002 safety delta

| Hazard | Mitigation | Residual risk |
|---|---|---|
| Forged source or modified event | Source-specific HMAC-SHA256, constant-time MAC comparison | Stolen symmetric key enables forgery; no independent identity attestation |
| Replayed or duplicated event | Atomic durable SQLite unique constraints on source+nonce and source+event_id | Database loss/rollback or cross-node unshared state reopens replay window |
| Stale or future-dated event | Bounded timestamp window | Host clock compromise/skew, malicious timestamp from compromised source |
| Oversized or malformed envelope | Canonical byte-size cap and strict schema | Ingress parsing happens before cap; external transport must bound raw payload |
| Store unavailable or corrupted | Reject without recommendation | Denial of service until storage repaired |
| AI recommendation used for actuation | `actionable=False`, no actuation interface | External downstream misuse is not technically prevented |
| Unbounded replay history | No automatic deletion of replay reservations | Storage exhaustion; retention policy requires a separate design |

Operational readiness: **NO-GO** for safety-critical autonomous control, production certification, and external exposure without an ingress gateway, key lifecycle, trusted clock, shared replay architecture where needed, and independent validation.

## AI-CORE-003 safety assessment
- HAZ-003-01: Crash during rotation can create uncertain key generation. Mitigation: durable PREPARED/COMMITTED phases, mandatory fail-closed fencing and explicit recovery. Residual: manual intervention required after committed-before-anchor crash.
- HAZ-003-02: Legacy admission bypass. Mitigation: replay reservation checks rotation phase and anchor/epoch in the same SQLite IMMEDIATE transaction. Residual: direct SQL writers and copied databases outside the protected API are not fenced.
- HAZ-003-03: Rollback of replay history. Mitigation: separately stored epoch anchor; rollback of only DB or only anchor detected. Residual: coordinated rollback of both cannot be detected without independently trusted monotonic hardware/service.
- HAZ-003-04: Filesystem failure and partial anchor writes. Mitigation: fsync file, atomic rename and directory fsync. Residual: hardware/filesystem guarantees vary.
- HAZ-003-05: Unauthorized recovery. Mitigation: explicit `approved=True` plus key fingerprint match. Residual: boolean approval is not authenticated operator authorization; production requires RBAC, signed authorization, audit trail.
- HAZ-003-06: Cross-process stale key registry. Mitigation: fingerprint validation for managed path. Residual: legacy admission can still use an old key when ACTIVE and its key mapping is stale; enforce managed admission exclusively in deployment.
- Readiness: NO-GO for safety-critical autonomous actuation. No external hardware anchor, HSM, trusted clock, cross-host quorum, or live TrainOS integration has been validated.

## AI-CORE-004 safety case and residual hazards
- **H-004-01: rollback of signed anchor plus database.** A software file cannot establish monotonicity if the adversary can restore an older correctly signed checkpoint. Mitigation required: TPM monotonic counter, external append-only witness, or independent transactional trust service. Status: OPEN / NO-GO.
- **H-004-02: legacy bypass.** TrustedAdmission rejects retired lifecycle keys, but its SQLite checks are not transactionally coupled to reservation across distinct connections. Direct ReplayStore.reserve and raw SQLite connections bypass independent-anchor authentication. Mitigation required: consolidate all writes behind a single transactionally enforced gateway; revoke direct DB access. Status: OPEN / NO-GO.
- **H-004-03: recovery authority compromise.** The demonstration helper runs with the recovery secret; in production signatures must be issued by a separate operator authority/HSM, with dual control and key revocation. Status: OPEN.
- **H-004-04: audit alteration.** Audit records are ordinary SQLite rows, without chained hashes or external attestation; they do not constitute tamper-evident evidence. Status: OPEN.
- **H-004-05: partial anchor writes.** Independent checkpoint advances before legacy checkpoint. A crash between updates creates a mismatch; admission fails closed, but reconciliation needs controlled offline tooling. Status: OPEN.
- **H-004-06: unverified hardware/OS behavior.** SQLite FULL sync and fsync are used, but power-loss guarantees depend on filesystem and hardware. No hardware crash tests performed. Status: OPEN.
- Security posture: development/test-only, no authorization for safety-critical autonomous control.

## AI-CORE-005 safety assessment
**NO-GO for safety-critical operation.** Fail-closed: bad MAC, clock skew, rotation fence, missing independent anchor, invalid gateway schema, audit tampering, and replay collisions prevent recommendation release. Atomicity relies on SQLite durable transactions and correct filesystem behavior. A software trigger cannot stop a privileged attacker who edits database schema/files. The HMAC chain authenticates surviving entries but **does not detect complete tail truncation or consistent database rollback** without a separate independently monotonic audit-head checkpoint. It also does not cover lifecycle_audit from Stage 004. Gateway enrolment is an explicit one-time operation and is not globally enforced across arbitrary separate databases. No physical fault injection, hardware secure element, external trusted clock, process-kill power-loss test, or TrainOS integration was performed. Fault hooks are simulated exceptions, not actual SIGKILL/power loss. Cross-process test verifies external SQLite connection rejection; true multi-process concurrent load remains untested.

## AI-CORE-006 safety case and residual risks
- HAZ-006-01: Truncated audit tail: HMAC checkpoint mismatch blocks admission when checkpoint is independently retained.
- HAZ-006-02: Crash after SQLite COMMIT but before checkpoint: mismatch fences all further admission; explicit reconciliation accepts one chained entry. Operator MUST verify the event externally before approving.
- HAZ-006-03: Privileged SQLite schema modification: ordinary trigger bypass is possible with DDL rights. Startup schema inspection catches missing triggers but does not prove exact trigger semantics.
- HAZ-006-04: Coordinated rollback of SQLite plus checkpoint, or disclosure of checkpoint key: NOT DETECTABLE by this software-only design.
- HAZ-006-05: Concurrent independent writers: checkpoint updates are not interprocess locked and can race. Deploy a single trusted writer, or add an OS-enforced service boundary and transactional checkpoint protocol.
- HAZ-006-06: `reconcile(authorized=True)` is a procedural gate, not cryptographic authorization; require a signed offline recovery grant before production use.
- HAZ-006-07: Checkpoint is a file, not an independent hardware monotonic register. No TPM/HSM or OS ACL validation performed.
- HAZ-006-08: A process crash between database commit and checkpoint update may cause a temporary denial of service. Fencing is intentional.

Deployment verdict: NO-GO for safety-critical autonomous actuation. Integration, OS isolation, key custody, and adversarial penetration testing remain outstanding.

## AI-CORE-007 safety assessment
- Hazard: unauthorized admission. Mitigation: kernel `SO_PEERCRED` allowlist, socket permissions and inherited gateway checks. Residual: same-UID clients and privileged users can access service; real filesystem isolation requires dedicated UID/ACL configuration.
- Hazard: recovery replay. Mitigation: checkpoint-bound HMAC and SQLite uniqueness of token ID. Residual: SQLite/checkpoint are not one atomic commit domain; recovery may fail closed after interruption; no hardware-backed monotonic counter.
- Hazard: IPC denial of service. Mitigation: size cap, socket timeout, serialized request handling. Residual: a slow authenticated client can delay service; no process supervisor, quotas or watchdog.
- Hazard: socket replacement. Mitigation: refuse to unlink pre-existing path. Residual: privileged attacker can alter socket directory; secure directory ownership is required.
- Hazard: key compromise. Recovery HMAC secret is supplied to server by trusted bootstrap; never place it in untrusted client. No HSM or external PKI integrated.
- Hazard: SIGKILL during admission. SQLite transaction rollback is tested in earlier Stage; crash after SQLite commit but before checkpoint write remains fail-closed and requires authorized reconciliation.
- Status: NO-GO for safety-critical use. Cross-UID isolation, OS sandboxing, service restart/recovery under supervisor, external anchor, TrainOS integration and hardware validation remain unverified.

## AI-CORE-008 safety case (NOT CERTIFIED)
Confirmed in the Linux root-capable test container: POSIX mode/owner checks; actual cross-UID write denial for private and socket directories; fail-closed rejection of symlink, incorrect mode, pre-existing socket directory entry, unexpected EUID, root service identity, and wrong socket location. Existing SIGKILL/SQLite rollback tests remain in regression. No dedicated unprivileged service instance was launched end-to-end; no live IPC connection was established between distinct UIDs under the isolated wrapper. `0700` socket directory plus `0600` socket prevents distinct-UID clients from connecting; this is a deliberate restrictive default, not an operational multi-user access policy. Parent-directory trust, ACLs, mount namespaces, SELinux/AppArmor, service unit hardening, durable fsync and key storage need separate assessment. Same-UID processes, root/CAP_DAC_OVERRIDE and privileged schema/file access remain in the threat model. `provision_service_layout` is not a secure recursive provisioning or TOCTOU-resistant openat2 implementation; checks can be raced by a privileged attacker. SIGKILL service restart and recovery integration are NOT verified for Stage 008. Safety-critical deployment remains NO-GO.

## AI-CORE-009 safety case (bounded)
- Validated on Linux in a root-capable test container: separate service/client UID, shared IPC GID, successful authorized IPC, denial of mismatched GID, and denial of direct private SQLite read by the client UID.
- SIGKILL child exits and restart-budget handling were tested; end-to-end crash/restart reconciliation of a live gateway was **not** established.
- File permissions cannot defend against root, CAP_DAC_OVERRIDE, a compromised service UID, namespace manipulation by a privileged actor, or shared-group privilege abuse. The IPC socket is group-accessible but operations still require peer UID authorization.
- Runtime permissions of existing storage files require an administrator-controlled provisioning step. Tests set modes during fixture initialization; production must provision without TOCTOU exposure.
- Existing `AdmissionIPCServer` and legacy APIs remain accessible; this is opt-in, not mandatory migration. External service manager, secrets handling, stale socket cleanup, key recovery, and independent rollback-resistant anchors remain unverified.
- Python multiprocessing `fork` emits DeprecationWarning under multithreaded pytest. No ResourceWarning observed. Prefer spawn/forkserver in production.
- Safety-critical readiness: NO-GO.

## AI-CORE-010 — Safety boundary and residual risks
Fail closed on live or unexpected socket, untrusted directory and gateway checkpoint mismatch. No implicit audit repair. The inode check followed by unlink is not race-free against another process able to modify the IPC directory. Exclusive directory access must be enforced by OS ownership and deployment. Direct imports of legacy APIs remain possible: mandatory production isolation requires packaging and OS-level policy, not merely an exported helper. This stage does not prove automatic full service restart, recovery of DB/checkpoint after all crash windows, production systemd isolation, or cross-UID E2E re-admission after restart. A privileged attacker can modify files and socket directory. Safety-critical readiness: NO-GO.

## AI-CORE-011 safety assessment
**NO-GO** for safety-critical deployment. Verified supervisor readiness and UID isolation depend on trusted executable, protected configuration, private socket directory, and service-side verification of SQLite and independent checkpoint. The supervisor cannot prove that an arbitrary supplied executable has implemented these checks. It must never auto-approve a DB-commit/checkpoint gap. Privileged processes can alter the filesystem; a coordinated rollback of SQLite and anchor remains undetectable without external monotonic trust. `production_admission` is an explicit opt-in registration guard, not universal legacy API fencing. The SIGKILL end-to-end test uses a minimal test IPC server, not the full anchored gateway; checkpoint recovery after SIGKILL remains unverified end-to-end. No hardware certification or TrainOS integration was performed.

## AI-CORE-012 safety assessment
- CONFIRMED (unit/integration): malformed permits rejected; replay rejected across a new authorizer instance; checkpoint mismatch blocks new production IPC object; crash-injection between permit consumption and checkpoint advancement leaves old permit unusable.
- NOT CONFIRMED: full end-to-end fresh-process service restart with SQLite re-open and subsequent admission under different UIDs; atomicity of SQLite and external checkpoint; OS-mandatory closure of direct legacy Python calls; hardware rollback resistance; resistance to root/privileged file modification.
- HAZARD: consumption recorded in SQLite but checkpoint update interrupted. MITIGATION: fail-closed and require a new operator-issued permit, never silently reconcile.
- HAZARD: coordinated rollback of SQLite and external checkpoint. MITIGATION REQUIRED: independent monotonic hardware/remote trust root; not implemented.
- RELEASE GATE: NO-GO for safety-critical operation.

## AI-CORE-013 safety assessment
- Hazard H013-01: untrusted client writes directly to database. Mitigation: dedicated non-root service UID, 0700 private directory, 0600 SQLite/key/checkpoint files. Verified with different UIDs in Linux root-enabled fixture. Does not resist root or file-owner compromise.
- Hazard H013-02: audit rollback or checkpoint tampering. Mitigation: independently HMAC-authenticated checkpoint and startup verification. Tampered checkpoint blocks socket publication. Coordinated rollback of both trust domains is not prevented.
- Hazard H013-03: process SIGKILL. Mitigation: fresh gateway and SQLite connections after restart; replay survives. Supervisor automatically restarts up to configured limit. A crash between commit and external checkpoint remains fail-closed; no automatic reconciliation.
- Hazard H013-04: socket substitution. Mitigation: private directory ownership/type checks and guarded stale socket reclamation. A privileged adversary can still alter filesystem objects; no proof against adversarial races with equal owner privilege.
- Hazard H013-05: bypass via legacy imports. Legacy library API is retained for compatibility and cannot be universally fenced against privileged direct callers. Production deployment must enforce file permissions and trusted entrypoint selection.
- Hazard H013-06: recovery token rollback. Permit consumption is durable in SQLite before external checkpoint advance. An attacker able to roll back SQLite and external trust anchors can defeat the replay defense. No HSM-backed monotonicity.
- Evidence: evidence/stage_validation_013.json and stage013_run*.txt. All guarantees limited to tested Linux environment.

## AI-CORE-016 safety disposition — NO-GO
Confirmed: cold PREPARED/no-commit recovery under a different UID; operator gate; journal and checkpoint verification; legacy production012 CLI disabled. Limitations: no actual SIGKILL at commit/checkpoint boundary verified for this stage; no committed-gap end-to-end proof; no multi-process recovery race proof; production013 CLI remains executable for compatibility; coordinated rollback of all trust stores remains outside the threat model; offline lock does not prevent an independently launched legacy writer. The external operator_verified boolean is a trusted-caller assertion, not an independently authenticated operator identity. No safety-critical deployment approval.

## AI-CORE-017 — verification limits (2026-11-14)

* The `production013` module executable is now disabled, matching `production012`.
  Its library API remains importable for backwards compatibility. Python callers
  with access to the service UID and signing keys are NOT prevented from calling
  legacy library functions directly; this is not an OS-level security boundary.
* The existing v013 tests were migrated to launch the journaled v015 production
  executable, rather than depending on the unsafe legacy entrypoint.
* Offline recovery remains an operator-asserted operation. No independently
  authenticated operator identity, cross-domain atomic commit, or trusted external
  anti-rollback device has been established.
* Full cumulative regression did not complete within the available execution
  budget; no assertion of full-stage completion or safety-critical readiness.

## AI-CORE-019 — Safety review
- Concurrent recovery: nonblocking `flock` and a second socket-state check under lock reduce double-recovery risk. A separately running admission server does not currently take the recovery lock, so this is not a full mutual-exclusion protocol with service startup.
- Permit replay: SQLite uniqueness and HMAC checks protect against ordinary repeated permits; a coordinated rollback of SQLite and external trust anchors remains out of scope without a monotonic external root.
- Socket/file substitution: lock symlink checks and socket checks are fail-closed under tested conditions; same-UID adversarial filesystem races and privileged attacks are not eliminated.
- Crash windows: Stage 018 fault injection is retained; the present Stage adds concurrent offline recovery checks, not a new complete crash-point matrix.
- Legacy Python imports are still callable by privileged/local code. Production isolation requires trusted entrypoints and OS permissions.
- Operator authentication is still represented by a trusted caller assertion; it is not independently authenticated by this module.
- Safety-critical readiness: NO-GO until all full regressions, cross-UID crash matrix, startup/recovery locking, and external monotonic rollback protection are demonstrated.

## AI-CORE-020 safety assessment — NO-GO
Confirmed: independent process lock contention and rejection of symlink/unsafe directory in targeted tests. Not confirmed: three successful cumulative regressions; concurrent service factory direct API bypass remains; lockfile replacement by a privileged adversary, coordinated storage rollback, crash matrix and multi-UID recovery were not fully retested. A lock is advisory and cannot fence malicious processes that ignore it. Atomicity across SQLite and external checkpoint remains unproven.
