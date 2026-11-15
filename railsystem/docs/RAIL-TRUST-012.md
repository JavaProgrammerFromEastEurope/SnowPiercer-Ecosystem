# RAIL-TRUST-012 — Independent Provider Integration & OS-Enforced Production Boundary

**Version:** RailSystem v0.22.0 (one functional Stage). **Disposition:** PARTIAL / BLOCKED / NO-GO.

## Requirements and acceptance conditions

| ID | Requirement | Evidence / outcome |
|---|---|---|
| RT012-01 | Four distinct, non-root UIDs for client, recovery IPC service, monotonic witness and permit authority | `validate_production_config()` and real four-UID Linux fork tests PASS; installed service manager unverified |
| RT012-02 | Missing independent providers, missing peer credentials, mismatched UID or socket replacement MUST deny, never fall back to local provider | New Unix-domain clients fail closed; negative tests PASS |
| RT012-03 | Remote CAS interface must reject rollback; remote permit endpoint must reject replays and ambiguous responses | RPC validation and volatile test-server scenarios PASS; *no independent provider certified or deployed* |
| RT012-04 | Startup must check protected state and remote services before publishing recovery IPC socket | `serve()` > strict config > broker `start()` with shared lock; tests PASS |
| RT012-05 | Recovery requests MUST verify actual client UID and isolate writable ledger/state from direct client access | Test with real client/service/witness/recovery UIDs PASS; only one interface tested |
| RT012-06 | SIGTERM cleanup and SIGKILL fail-closed restart, interrupted CAS and permits | tests PASS using separate-process volatile provider fakes; power loss and remotely durable state unproven |
| RT012-07 | Production service must be managed by OS independently of the client | systemd unit **example**, runtime binary and deployment contract supplied; **NOT ACTIVATED**, systemd unavailable in current container |
| RT012-08 | Existing Stage APIs/imports remain stable | Three full cumulative strict regressions required; results stored in evidence |
| RT012-09 | Legacy direct production write paths must be OS denied | Client-UID direct state access denied in test; *service-owner import bypass remains possible*. **Unclosed** |
| RT012-10 | Independent rollback protection and host-power-failure crash consistency | Not proven, production BLOCKED/NO-GO |

## Architecture

Four OS user identities: `rail-client` (client), `rail-service` (IPC and private SQLite owner), `rail-witness` (external CAS witness), `rail-recovery` (separate permit-ledger authority). All four IDs must differ and be non-root. `rail-ipc` is a dedicated group for Unix transport; permissions: private state 0700, IPC dirs 0750, provider and broker sockets 0660. Client receives only transport access; not access to SQLite, phase journal, local anchor, signed recovery permit/private resources or witness state.

`railsystem.provider_ipc.AuthenticatedUnixRPC` calls Unix-domain sockets with exact peer UID and GID verification via Linux `SO_PEERCRED`; rejects wrong modes, ownership, symlinks, swapped socket inodes, malformed or oversized frames, unrecognized envelopes, transport errors and timeouts. Bounded request and response, no arbitrary JSON commands. External providers must *themselves* authenticate the inbound service UID and enforce durable linearizable CAS/consume-once; clients only authenticate the remote service identity, **not its storage**. OS verification does not attest remote persistence or different failure domains.

`UnixAnchorClient` preserves `IndependentAnchor.read()/advance()`; `UnixPermitLedgerClient` preserves `IndependentPermitLedger.check_ready()/consume_once()`; both are injection-compatible with existing `unified_admission.admit/recover` and `PrivilegedRecoveryBroker` without changing old method signatures. **The source SHA-256 baseline now includes `systemd/` and `deployment/` whenever present (older roots without them remain valid), preventing unnoticed modifications of the shipped OS-boundary templates in the signed release baseline. No production server** for those contracts is bundled. Test fakes (tests/helpers_012.py) hold in-memory state, and are deliberately NOT production backends.

`os_boundary.validate_production_config(config)` validates the exact schema, four distinct non-root UIDs, current service EUID, owner/group/mode of state/transport folders and 0600 or 0400 service-owned out-of-band credentials; it checks both provider endpoints before socket publication. `service_runtime` starts the broker without privilege escalation or self-daemonizing, and accepts `RECONCILE` only, using previously supplied signed permit; it never takes a permit or arbitrary operation from a client. SIGTERM closes an owned socket; SIGKILL intentionally leaves a stale socket that prevents restart until an independently authorized operator diagnoses and removes it. `service_runtime.main` exits 2 on failure rather than silently falling back.

## Systemd service-manager examples (not deployed)

The directory `systemd/` contains fail-closed examples for service, witness and permit authority. Witness/permit executable paths are deliberately **not provided**, because a durable independent provider with storage and credentials outside the local host rollback domain was not supplied. Separate `rail-client` is a principal, not a daemon. The recovery unit uses `User=rail-service`, `Group=rail-ipc`, `NoNewPrivileges`, `ProtectSystem`, `ProtectHome`, `ReadWritePaths`, non-root execution and `Restart=no`. The OS operator must supply account provisioning, directory ownership, confined executable and matching `production.json` delivered via `LoadCredential`; `LoadCredential` file mode/owner must satisfy `validate_production_config`. The service does not create UID accounts or install units. Units are **examples**, not live operational controls. In this container PID 1 is supervisord, systemd is offline.

Provisioning contract (illustrative): `deployment/roles.example.json` with exact per-host UIDs and paths. NEVER use those numeric example UIDs directly in production without provisioning. `python -m railsystem.service_runtime --config /path/to/protected/production.json` blocks unless every required provider, protected directory and credential passes checks.

## Recovery, startup and fault semantics

Existing `unified_admission` uses one file lock, SQLite `PREPARED`, external CAS, local atomic-anchor replacement, SQLite `IDLE`; recovery burns a signed permit through the external `consume_once` before reconciling and commits the local digest in SQLite. The sequence is intentionally not a multi-resource atomic commit. If a remote CAS or permit response is ambiguous, admission/recovery fail closed. If SIGKILL occurs after permit consumption, the permit cannot be used again **as long as the independent provider stays truthful and durable**. Test matrix now includes actual SIGKILL after a cross-UID Unix witness CAS and after cross-UID permit consumption, SIGTERM cleanup, SIGKILL stale socket, and previous local 8-point admission and 5-point recovery SIGKILL matrix.

## Safety analysis and adversarial residuals

| Hazard | Mechanism | Unclosed safety issue |
|---|---|---|
| Forged witness, replay, rollback | Kernel peer UID + exact socket file checks + typed CAS | Compromised witness UID or writable remote store, host snapshot rollback, mount namespace TOCTOU, false provider durability claim |
| Permit replay | Authenticated authority UID + consume-once contract | Test provider volatile; no real durable independent consumption authority; service may resume with a new recovery permit only by operator |
| Cross-UID write bypass | Private `0700` state, non-root service, SO_PEERCRED | Service-owner code can import legacy write APIs; hard OS-enforced universal production entrypoint isolation NOT proven |
| Untrusted client / IPC replacement | UID allowlist, bounded recv, owner/mode/inode checks, no automatic socket cleanup | Provider-side client ACL not verified against production backend; shared group membership and ancestor path replacement need OS deployment auditing |
| Startup/crash races | Common state lock in broker and `unified_admission`, PREPARED fence | No multi-host lock, power-loss proof, independently deployed service manager or cryptographically witnessed phase journal |
| Physical railway hazard | Non-actuating software only, release BLOCKED, NO-GO | No validated train-control software, HIL, EN 50126/50128/50129 evidence, independent assessor or regulatory approval |

## Honest evidence boundary

Locally verified: Linux `SO_PEERCRED` and four real UID restrictions, live Unix RPC, CAS/replay semantics **with volatile test-only processes**, real SIGTERM/SIGKILL and strict cumulative regression. Not verified: true independent rollback-resistant hardware/remote provider, systemd activation, power loss, compromised service/witness UID, direct service-owner legacy bypass, complete boundary-to-boundary SIGKILL matrix across deployed provider systems, production safety case. **Do not authorize production release or real rail operations.**
