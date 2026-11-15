# AI-CORE-001 requirements and traceability

| ID | Requirement | Verification |
|---|---|---|
| AI-REQ-001 | Accept strictly defined observation schema | test_reject_invalid |
| AI-REQ-002 | Deterministically map severity to recommendation | test_severity_matrix |
| AI-REQ-003 | Never produce executable actions | test_non_actionable |
| AI-REQ-004 | Produce stable evidence digest | test_deterministic_evidence |
| AI-REQ-005 | Avoid modifying input | test_input_is_not_modified |
| AI-REQ-006 | Support defined subsystem source vocabulary | test_all_sources |

# AI-CORE-002 requirements and traceability

| ID | Requirement | Verification |
|---|---|---|
| AI-REQ-007 | Authenticate source-bound observation via HMAC-SHA256 | test_tampering_and_wrong_key, test_source_binding |
| AI-REQ-008 | Reject nonce and event-id replays atomically | test_exact_replay, test_event_id_replay_with_fresh_nonce, test_concurrent_replay_only_one_admitted |
| AI-REQ-009 | Persist replay state across process restarts | test_replay_survives_restart |
| AI-REQ-010 | Enforce freshness and future skew | test_stale_and_future_boundaries |
| AI-REQ-011 | Bound envelope and reject malformed input | test_oversize_rejected, test_malformed_envelopes |
| AI-REQ-012 | Fail closed on replay-store or clock failure | test_storage_failure_closed, test_bad_clock_fail_closed |
| AI-REQ-013 | Preserve original assess API and non-actionable results | test_valid_and_read_only, test_core.py |
| AI-REQ-014 | Isolate replay namespace per authenticated source | test_cross_source_independent_replay_namespace |

## AI-CORE-003 requirements
- AI-003-R01: durable PREPARED fence precedes any key generation change.
- AI-003-R02: COMMITTED generation and epoch change atomically in SQLite.
- AI-003-R03: ACTIVE only after external anchor catches up and the key is provisioned.
- AI-003-R04: legacy ReplayStore.reserve must reject writes while rotation is incomplete or anchor mismatched.
- AI-003-R05: recovery requires explicit approval and matching generation key; mismatched epoch is not auto-repaired.
- AI-003-R06: replay history is never cleared by rotation.
- AI-003-R07: bootstrap is explicit and forbidden if existing history or generation exists.

## AI-CORE-004 requirements
- AI-004-REQ-01: Opt-in independent authenticated checkpoint shall be verified by HardenedRotationManager before admission.
- AI-004-REQ-02: Independent checkpoint shall advance monotonically on successful key rotation; any mismatch shall fail closed.
- AI-004-REQ-03: Recovery shall require a valid HMAC-SHA256 authorization bound to source, key hash, generation, epoch and one-time token identifier.
- AI-004-REQ-04: Recovery token identifiers shall be recorded and rejected upon reuse.
- AI-004-REQ-05: Legacy TrustedAdmission shall reject keys inconsistent with the current lifecycle generation fingerprint.
- AI-004-REQ-06: Recovery and rotation attempts shall be auditable; audit log is informational, not tamper-evident.
- AI-004-REQ-07: Existing AI-CORE-001..003 APIs shall remain usable.

## AI-CORE-005 Mandatory Admission Gateway
- AI-REQ-005-01: enrolled gateway shall reject unsigned/invalid or stale observations before state mutation.
- AI-REQ-005-02: gateway shall verify lifecycle and independent anchor inside a SQLite write transaction.
- AI-REQ-005-03: replay reservation and append-only HMAC audit entry shall commit or roll back together.
- AI-REQ-005-04: enrolled `seen` table shall reject ordinary legacy and external-connection INSERT/UPDATE/DELETE operations.
- AI-REQ-005-05: gateway shall fail closed on missing triggers, audit-chain modification, or incomplete rotation.
- AI-REQ-005-06: existing AI-CORE-001–004 APIs remain importable and tests remain green.

## AI-CORE-006 — Independent Audit Anchoring
- AI-006-R01: An authenticated checkpoint SHALL bind the audit sequence and HMAC head.
- AI-006-R02: Missing, corrupt, or divergent checkpoint SHALL fence admission.
- AI-006-R03: A post-commit/pre-checkpoint crash SHALL require explicit reconciliation.
- AI-006-R04: Reconciliation SHALL permit at most one chained pending entry and require explicit authorization.
- AI-006-R05: Direct SQLite writes through a separate ordinary connection SHALL be rejected by enrolled triggers.
- AI-006-R06: SIGKILL during an uncommitted SQLite transaction SHALL leave no committed partial transaction.

## AI-CORE-007
- AI-007-R01: reject IPC peers whose kernel-reported UID is not allowlisted.
- AI-007-R02: accept only bounded newline-framed JSON requests and three explicit operations.
- AI-007-R03: recovery requires a separately allowlisted UID and checkpoint-bound HMAC authorization.
- AI-007-R04: recovery permit identifiers are single-use and persisted.
- AI-007-R05: retain prior public APIs and fail closed on checkpoint mismatch.
- AI-007-R06: deployment shall enforce service UID ownership and prevent client access to SQLite, keys and anchors (deployment prerequisite, NOT verified by unit tests).

## AI-CORE-008 requirements
- AI-CORE-008-R01: Service private directory and IPC directory must be owned by service UID and mode 0700.
- AI-CORE-008-R02: Immediate private regular files must be owned by service UID and mode 0600; symlinks and special files rejected.
- AI-CORE-008-R03: New isolated service wrapper must reject root and unexpected effective UID before socket bind.
- AI-CORE-008-R04: Pre-existing socket directory entries must fail startup preflight.
- AI-CORE-008-R05: Existing public APIs remain functional; full regression must run with ResourceWarning escalated.

## AI-CORE-009 — Cross-UID IPC Authorization & Crash-Safe Service Recovery
- AI-009-R01: service process must run as a non-root UID distinct from the IPC client UID.
- AI-009-R02: private state must be owned by the service and accessible only to it (directory 0700, files 0600).
- AI-009-R03: IPC directory must be 0710 with designated shared GID, socket 0660; peer UID authorization remains mandatory.
- AI-009-R04: supervisor must bound restart attempts and fail closed when the restart budget is exhausted.
- AI-009-R05: legacy server behavior must remain unchanged unless the cross-UID service is explicitly selected.

## AI-CORE-010 — Crash recovery boundary
- AI-010-01: Refuse production registration under UID 0 or incorrect effective UID.
- AI-010-02: Verify gateway trust state before making recovered IPC available.
- AI-010-03: Reject symlinks, regular files, foreign owners and active sockets at restart.
- AI-010-04: Reclaim only a demonstrably disconnected Unix socket in a protected directory.
- AI-010-05: Never automatically reconcile a mismatched audit checkpoint.

## AI-CORE-011 — Recovery orchestration and production fencing
- AI-011-R1: A production supervisor SHALL launch the service under a non-root dedicated UID and verify socket ownership and `verify` IPC readiness before considering it ready.
- AI-011-R2: On abnormal exit the supervisor SHALL create a fresh child, enforce a finite restart budget, and fail closed when readiness is not established.
- AI-011-R3: Production registration SHALL reject direct legacy gateway admission; library gateway APIs remain available for non-production compatibility.
- AI-011-R4: A mismatched audit checkpoint SHALL NOT be automatically reconciled by the supervisor.
- AI-011-R5: OS-level directory ownership/mode and socket inode SHALL be checked; the child MUST verify its SQLite and external anchors before binding.

## AI-CORE-012
- AI-012-REQ-01: Production IPC must require an anchored gateway and verify it before publishing the socket.
- AI-012-REQ-02: Recovery permits must be authenticated, bound to checkpoint state, and consumed durably before external checkpoint advancement.
- AI-012-REQ-03: Reused permits, malformed signatures, ambiguous audit history and mismatched checkpoint must fail closed.
- AI-012-REQ-04: Keep pre-existing library APIs unchanged; production registration must not expose direct gateway admission.
- AI-012-REQ-05: Independently verify restart and cross-UID deployment before claiming full end-to-end readiness (OPEN).

## AI-CORE-016 — cold recovery (partial)
- Recovery is offline, requires explicit operator verification, a signed checkpoint-bound permit, exclusive flock and a non-root service identity.
- A PREPARED journal blocks normal service startup. Cold bootstrap checks audit chain and independent rotation anchor before recovery.
- Committed but unanchored single audit event uses durable permit consumption before checkpoint reconciliation; no-commit recovery also burns its permit.
- No recovery is authorized from production IPC. Legacy production012 CLI is fenced; production013 remains available for historical regression and is NOT production-safe.

## AI-CORE-017
- AI017-R1: Legacy v012/v013 executable entrypoints MUST reject direct invocation.
- AI017-R2: Legacy library imports MUST remain compatible.
- AI017-R3: Production v015 remains the journaled admission executable.
- AI017-R4: Incomplete recovery and untested crash windows MUST remain NO-GO.

## AI-CORE-019 — Concurrent recovery and regression stabilization
- R019-01: offline recovery MUST refuse a concurrently held recovery lock without waiting indefinitely.
- R019-02: after acquiring the lock, recovery MUST recheck socket occupancy before opening SQLite.
- R019-03: invalid or replayed recovery permits MUST NOT transition PREPARED to CLEAN.
- R019-04: recovery lock symlinks and unsafe ownership/mode MUST be rejected.
- R019-05: cumulative tests MUST be executed with ResourceWarning and DeprecationWarning promoted to errors, with run-specific logs and explicit timeout status.

## AI-CORE-020 — unified startup/recovery lock
- The supported production015.run entrypoint MUST hold recovery016.lock from before constructing SQLite/gateway objects until IPC shutdown.
- Offline cold_recover MUST acquire the identical nonblocking lock; concurrent acquisition MUST fail closed.
- Lock inode, ownership, link count and mode MUST be validated; symlink locks MUST be rejected.
- Direct library create_service/serve and legacy Python APIs remain outside the mandatory runtime lock boundary; production deployments MUST prohibit these paths through process entrypoint policy.
