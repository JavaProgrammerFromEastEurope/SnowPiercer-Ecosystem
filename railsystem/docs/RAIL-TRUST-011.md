# RAIL-TRUST-011 — Privileged Recovery Broker & Durable Permit Consumption

**Release:** RailSystem v0.21 (cumulative on v0.20)  
**Classification:** PARTIAL; production software release **BLOCKED**; physical rail operations **NO-GO**.

## Scope and requirements

| ID | Normative requirement | Verification status |
|---|---|---|
| RT011-01 | Recovery IPC MUST authenticate kernel-issued peer credentials and use an explicit UID allowlist. | Linux root-host test PASS; no independent deployment assessment |
| RT011-02 | The service MUST own a private 0700 state directory, separate from an operator-provisioned 0750 IPC directory and 0660 group-gated Unix socket. | Local ownership/mode and real cross-UID tests PASS |
| RT011-03 | The IPC request MUST contain only `RECONCILE\n`; recovery permit and signer public key MUST be provisioned out of band. | Negative tests PASS |
| RT011-04 | Independent external anchor and independent durable permit-consumption service MUST be available; otherwise startup MUST fail closed. | Interface-level tests PASS; no production providers provisioned |
| RT011-05 | Permit MUST be Ed25519-signed, sequence-bound and consumed independently and at most once BEFORE local recovery commit; ambiguous/no response MUST NOT allow PASS. | Test-double negative/replay/crash cases PASS; independent durability unproven |
| RT011-06 | Startup, admission and recovery MUST reuse `admission.lock`; any stale/socket replacement MUST NOT be unlinked automatically. | Tests for overlap, SIGKILL and replacement PASS; full host authority unproven |
| RT011-07 | Legacy library APIs MUST remain importable; production MUST NOT invoke their unanchored release/recovery methods. | Compatibility regression PASS; enforcement across external clients unproven |
| RT011-08 | Crash-point injection MUST use real SIGKILL, recording surviving SQLite/anchor/permit states; no silent partial-release success. | Software fault matrix PASS; power-loss/hardware guarantees untested |

These requirements are Stage-scoped. The historical `requirements/registry.json` remains byte-compatible with v0.20: its legacy validator and tests intentionally prescribe exactly 12 original entries; migration to a versioned registry is deferred.

## Interfaces and process model

`railsystem.durable_permits.IndependentPermitLedger`
- `check_ready()` authenticates and verifies availability of an independently administered ledger. The default raises `PermitLedgerUnavailable`.
- `consume_once(digest, *, sequence, action)` performs a durable, linearizable, authenticated one-use insert. Must return **literal** `True` only for first consumption, **literal** `False` for a known replay; any timeout or uncertain state MUST raise. Default fails closed. Neither production backend nor cryptographic transport attestation is bundled.
- Receipt persistence **MUST NOT** share a rollback/failure domain with SQLite, the local anchor, the host filesystem, or client-provided input. A shared-host test-file implementation is *not* a compliant provider.

`railsystem.privileged_recovery.PrivilegedRecoveryBroker(state_dir, ipc_dir, *, transport_gid, allowed_uids, provider, permit_store)`
- Requires running under a dedicated trusted service UID with OS-provisioned 0700 state directory; 0750 IPC directory owned by the service with designated transport group; 0660 socket assigned to that group. Service UID must not be in the client UID allowlist.
- `start()` checks external services under `admission.lock`; pre-existing socket pathname causes BLOCKED (never auto-unlink unknown objects).
- `handle_one(permit=..., recovery_public_key=...)` identifies the connecting peer via Linux SO_PEERCRED, authorizes exact UID, accepts only `RECONCILE\n`, then holds the common lifecycle lock through `unified_admission.recover(..., _lock_held=True, permit_store=...)`. No recovery permit, sequence or recovery key is accepted from the client socket.
- `close()` only unlinks the same socket identity originally published. Separate OS service manager must provision identities, supervise and restart the service, supply the out-of-band signed permit and independently authenticated providers.
- Only one connection is handled per call; this is a service endpoint **library**, not an OS-level daemon or verified recovery orchestration platform.

`railsystem.unified_admission.recover(..., permit_store=None, _lock_held=False, kill_at=None)` retains legacy argument compatibility. `permit_store=None` preserves the previous local SQLite permit behavior for *nonproduction* callers; **this legacy path is NOT rollback-safe and MUST NOT be exposed as a production action**. The new broker always supplies a nonempty independent permit store and does not fall back to local-only consumption. `_lock_held` is private and requires ownership of `admission.lock`.

`railsystem.unified_admission.admit(..., kill_at=None)` preserves existing arguments and adds SIGKILL injection points for tests. These are diagnostic hooks and never authorization features. The existing `fault=` exit-code behavior is unchanged.

## Crash-consistent recovery order

1. OS service identity and UID peer authentication; IPC socket identity and phase-journal checks under shared lifecycle lock.
2. Read SQLite `PREPARED`, signed scope-bound permit, local anchor and externally authenticated CAS state; reject mismatches.
3. **Durably consume** permit digest with independent one-use service before any recovery anchor or SQLite commit.
4. If external CAS advanced, finish atomic local-anchor replacement (`fsync` + directory sync); otherwise retain old anchor.
5. Under SQLite `BEGIN IMMEDIATE`, reconcile phase journal/replay state and record local copy of consumed digest; commit using `synchronous=FULL`.
6. Reply `RECOVERED` only after completed local commit; otherwise `BLOCKED`.

**Failure semantics:** crash after external permit consumption but before SQLite final commit burns the permit. Recovery remains fenced and requires a freshly authorized, differently signed permit. There is no automatic retry of the consumed permit. This is intentional fail-closed behavior rather than a two-resource atomic commit. An ambiguous remote outcome likewise requires independent reconciliation; the package offers no proof of remote linearizability.

## Fault and adversarial coverage

Real `os.kill(SIGKILL)` in forked processes, with negative signal exit codes:
- admission: `before_prepare`, `after_prepare`, `before_external`, `after_external`, `before_local`, `after_local`, `before_final_commit`, `after_final_commit` (mocked test-only release-gate success; real Ed25519 verification).
- recovery: `before_permit_consume`, `after_permit_consume`, `after_recovery_anchor`, `before_recovery_commit`, `after_recovery_commit`.
- lifecycle lock: real killed owner; lock re-acquisition.
- IPC: killed server leaves stale socket and triggers fail-closed restart.

Linux root-host cross-UID test: trusted service runs as UID 0 in test-only environment; two real client processes are dropped to distinct numeric UIDs, granted a dedicated transport GID. Kernel credentials reject the nonallowlisted UID; authorized UID triggers only the out-of-band-signed recovery request; state directory is unreadable by either client. This test does **not** establish the suitability of running the production service as UID 0; use a restricted dedicated service identity in deployment.

Negative tests also cover forged/modified signature, unavailable services, tampered socket path/permissions/GID, concurrent starts, legacy IPC command, local SQLite permit-table rollback with a test ledger retained, and external permit reuse.

## Safety analysis / outstanding hazards

| Hazard | Mitigation in this Stage | Remaining risk |
|---|---|---|
| Permit replay after local SQLite rollback | Separately provisioned `consume_once` required for broker | No independent ledger deployed; test ledger is rollbackable |
| Split-brain between anchor, SQLite and permit ledger | PREPARED fence; one lock; burn permit before commit | External systems are not one atomic transaction; remote ambiguous acknowledgement |
| Unauthorized cross-UID recovery | 0750/0660 group-gated IPC plus SO_PEERCRED UID allowlist | Service-manager, namespace, container, and privilege separation not independently assessed |
| SIGKILL during critical transitions | Deterministic real-SIGKILL fault injection and fail-closed state checks | Kernel/storage power loss, filesystem durability and all IPC timing interleavings unproven |
| Socket or file path substitution | owner, gid, mode, inode, no automatic cleanup of unknown path | Privileged adversary, mount namespace substitution and all TOCTOU windows unproven |
| Legacy production bypass | New broker dispatches solely to protected recover; release CLI remains fail closed without anchor | `release_gate.evaluate`, `trusted_admission.admit`, `anchored_admission.admit_anchored/recover`, `production_fencing.recover_with_attestation`, `unified_admission.recover` remain callable by service-owner processes for compatibility. No OS-enforced universal production fencing demonstrated |

**Production gate:** BLOCKED. No independently protected CAS provider or permit ledger, no formally configured OS service manager/witness separation, no full fault matrix at real network/CAS/SQLite/fsync boundaries, no power-loss certification, no interlocking or railway hardware tests, no regulatory/independent safety approval. **Rail physical operation: NO-GO**.
