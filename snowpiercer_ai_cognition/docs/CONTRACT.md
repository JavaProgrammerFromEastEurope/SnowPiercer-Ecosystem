# Observation / Recommendation contract v1

Input: mapping with **exactly** `event_id`, `source`, `severity`, `description` (strings).
- `event_id`: 1..128 ASCII letters, digits, hyphen, underscore, dot.
- `source`: trainos, rail, energy, life_support, logistics, security, island, operations.
- `severity`: info, warning, critical.
- `description`: 1..2048 characters, no ASCII control characters.

Output: `event_id`, `decision` (OBSERVE/INVESTIGATE/ESCALATE), `reason_code`, `evidence_sha256` (SHA-256 of canonical UTF-8 JSON input), `actionable` (always false).

Compatibility: pure Python 3.9+; no external dependencies. No networking, I/O, actuation, authorization or TrainOS imports. Unknown input fields rejected (fail closed). Caller must enforce identity, provenance, freshness, replay protection, and authorization before submitting observations; SHA-256 is an integrity fingerprint, **not** authentication. No guarantees of semantic truth of observations.

# Authenticated admission contract v2 (AI-CORE-002)

Original `assess(payload)` and v1 observation/recommendation shapes are unchanged. **Important:** `assess` remains an untrusted pure helper; only `TrustedAdmission.admit` applies authentication and replay checks. Integrators must not bypass the admission boundary.

Producer: `signed_envelope(observation, timestamp, nonce, key)` produces mapping with exactly `observation`, `timestamp`, `nonce`, `mac`. MAC is lowercase hex HMAC-SHA256 over canonical UTF-8 JSON of the other three fields (`sort_keys=True`, `ensure_ascii=False`, compact separators, `allow_nan=False`). Timestamp is integer Unix seconds, nonce is 16..128 ASCII alphanumeric or `-_.`, and each source must have an independently provisioned secret of >=32 bytes. **This is symmetric authentication, not public-key signatures or independent hardware attestation.**

Consumer: `TrustedAdmission(keys, ReplayStore(sqlite_path), clock=...)`; `admit(envelope)` returns original non-actionable `Recommendation` or raises `AdmissionRejected` with a stable reason. Total canonical JSON envelope size <=8192 bytes; default accepted timestamp window is [now-300, now+30] seconds, inclusive. Unknown fields are rejected. The key is selected by the validated observation source. Successful authentication and freshness precede atomic SQLite uniqueness reservation of `(source,nonce)` and `(source,event_id)`; only then is recommendation produced. Replay state persists until explicit external lifecycle management; **do not delete/prune replay rows without designing retention and source sequence semantics**. SQLite durability uses `synchronous=FULL`; deployment must place the database on reliable persistent storage with appropriate access controls and backups. Caller owns the store lifecycle and must call `close()`.

No network endpoint, model training, remote identity federation, key rotation, quota-per-source, distributed replay coordination, or direct actuation is implemented. Envelope size is checked after Python object materialization: HTTP ingress must impose byte caps before JSON parsing. Keys are supplied in-process and must be protected and rotated by the integrator. Time authority is the supplied host clock, not a trusted time service. Separate processes may use the same SQLite file with database locking; distributed nodes require shared replay coordination. No guarantee of semantic truth of authenticated claims.

## AI-CORE-003 lifecycle contract
`RotationManager(store, anchor_path, keys, bootstrap=False)` creates/validates lifecycle metadata. For first-time empty database only, set `bootstrap=True`. `provision(source)` establishes generation 1. `rotate(source,new_key,fault=None)` journals PREPARED -> COMMITTED -> ACTIVE, with fault injection values `prepared`, `committed`, `anchored` for tests. `recover(source,key,approved=True)` is an explicit operator-controlled reconciliation; refuses divergent anchor/DB epochs. `admit(envelope,clock=...)` enforces lifecycle checks before normal authenticated admission. Legacy `TrustedAdmission` is fenced at `ReplayStore.reserve` for the same SQLite database. Keys remain externally provisioned; the DB stores only HMAC key fingerprints, not secrets. The anchor file must be protected in an independent rollback domain. All APIs from 001 and 002 remain importable.

## AI-CORE-004 contract
- `IndependentAnchor(path, secret: bytes)` requires independently provisioned secret >= 32 bytes. `read() -> int`; `advance(epoch: int, bootstrap=False)`.
- `HardenedRotationManager(store, anchor_path, keys, *, independent_anchor, recovery_secret, bootstrap=False)` extends `RotationManager`.
- `recovery_token(source, key, token_id)` is an offline signing helper for demonstrations; production must isolate authorization secret outside the service.
- `recover(source, key, *, token_id, authorization)` requires valid single-use MAC. `approved=True` alone is never sufficient.
- `rotate(source, new_key, fault=None)` preserves fault hooks and dual-checkpoint ordering; on failure admission is fenced by hardened manager.
- `TrustedAdmission` performs lifecycle fingerprint check when rotation table exists. Direct `ReplayStore.reserve` and raw SQLite writes are outside this guarantee.

## AI-CORE-005 Gateway API
`MandatoryAdmissionGateway(manager: HardenedRotationManager, audit_secret: bytes, *, clock=None, bootstrap=False)` enrolls a new database only when `bootstrap=True`; reopening uses `bootstrap=False`. `admit(envelope, *, fault=None)` returns the existing read-only Recommendation. `verify()` returns `(audit_entry_count, audit_head_mac)` and fails closed on corruption. Caller owns and closes ReplayStore. `audit_secret` must be independently provisioned and persist across restarts. `fault` is for testing only. No API provides physical control commands.

The SQLite trigger enforcement is **software-level**. A privileged actor capable of dropping triggers or modifying the DB file can bypass it. Direct calls to `assess()` remain intentionally available as offline, non-admitting analysis, and are not equivalent to trusted admission. The old `TrustedAdmission.admit()` cannot successfully reserve in an enrolled store through the default trigger.

## AI-CORE-006 public contract
`AuditCheckpoint(path, key: bytes)` requires a separately provisioned 32+ byte secret. `read()` returns `(seq, head)` or raises `RecoveryRequired`. `write(seq, head, bootstrap=False)` durably replaces the checkpoint, enforcing single-step monotonic progression; it is **not** an anti-rollback hardware primitive.

`AnchoredAdmissionGateway(manager, audit_secret, checkpoint=..., clock=..., bootstrap=False)` preserves the inherited `admit(envelope)` and `verify()` interface. `admit()` fails closed on mismatch. `reconcile(authorized=True)` accepts exactly one verified, chained, unanchored committed audit record. Authorization is an in-process boolean and MUST NOT be treated as cryptographic or operator identity verification.

The database commit and checkpoint replacement are **not atomic across failure domains**. An unexpected exit between them creates a fenced state. Only one trusted writer/process is supported; concurrent independent checkpoint writers are not supported.

## AI-CORE-007 IPC contract
Linux-only `AdmissionIPCServer(gateway, socket_path, allowed_uids={...}, recovery_secret=..., recovery_uids={...})`; call `serve(ready=threading.Event())`, `stop()` to request graceful exit. Socket must not preexist. Request: one UTF-8 JSON object followed by newline, <=65536 bytes. Operations: `{"op":"admit","envelope":...}`, `{"op":"verify"}`, `{"op":"recover","permit":...}`. Response: JSON line with `ok` and optional `seq`, `head`, `decision` or `error`. `recovery_permit(secret, token_id, seq, head)` creates a signed permit outside the untrusted client. A permit is bound to the *previous* checkpoint head and authorizes one-entry reconciliation only. Error names are diagnostic, not a stable public API. Client identity is OS UID, not an application-provided identity string. The socket mode is 0600, and its parent directory must be secured by deployment.

## AI-CORE-008 API
`provision_service_layout(private_dir, socket_dir, service_uid=None, service_gid=None)` provisions empty directories and validates modes/ownership. `verify_service_layout(private_dir, socket_dir, service_uid=None)` checks directories and immediate entries; raises `IsolationError` on violation. `verify_runtime_identity(service_uid, private_dir, socket_dir)` rejects root and unexpected EUID. `IsolatedAdmissionIPCServer(gateway, socket_path, *, service_uid, private_dir, socket_dir, allowed_uids, recovery_secret, recovery_uids=())` wraps the existing IPC server with preflight on construction and serve. No silent privilege drop is performed. Caller is responsible for a trusted parent path, UID provisioning, file creation policy and service manager.

## AI-CORE-009 API
`verify_cross_uid_layout(private_dir, socket_dir, *, service_uid, ipc_gid)` verifies ownership, modes, and absence of unexpected files. `CrossUIDAdmissionService(gateway, socket_path, *, private_dir, socket_dir, service_uid, ipc_gid, allowed_uids, recovery_secret, recovery_uids=())` is an opt-in admission server. Its socket uses mode 0660 and IPC GID, while `SO_PEERCRED` UID allowlists still apply. `supervise_process(factory, *, stop_event, max_restarts=3, delay=0.05)` restarts nonzero-exit child processes within a finite budget. Factory must return a fresh unstarted multiprocessing Process each time. The supervisor does not itself reconstruct or validate an existing gateway: that remains the child entrypoint's responsibility.

## AI-CORE-010
`reclaim_stale_socket(path, *, service_uid, socket_dir) -> bool`: returns True only for removed stale Unix socket; raises `IsolationError` for unsafe or uncertain state. Caller must exclusively control the IPC directory. `RecoverableCrossUIDService` verifies gateway and service UID at construction and at serve startup. `production_gateway_only(gateway=..., service_uid=...)` validates identity and gateway; it does not revoke access to existing Python APIs.

## AI-CORE-011 API contract
`AdmissionSupervisor(command, socket_path, service_uid, max_restarts=2, startup_timeout=5)` starts a fresh OS process using Linux `subprocess.Popen(user=service_uid)`. `run(stop_event=...)` is blocking and returns the restart count on graceful stop; raises `IsolationError` on invalid startup or exhausted budget. Readiness requires an authenticated-by-filesystem UID socket plus successful `{'op':'verify'}` IPC reply. The supervisor itself does not reconcile checkpoint state. `production_admission(gateway, production=True)` always raises `IsolationError('PRODUCTION_IPC_REQUIRED')`; default/non-production returns the original gateway. Existing library APIs are unchanged. These contracts do not enforce a system-wide ban on direct imports, filesystem writes, or privileged bypass.

## AI-CORE-012 contract
`ProductionAdmissionIPCServer(gateway, socket_path, allowed_uids, recovery_secret, recovery_uids=())` requires an anchored gateway, performs `verify()` at construction and before `serve()`, and uses `DurableRecoveryAuthorizer` for `recover`. `DurableRecoveryAuthorizer.reconcile(permit)` verifies the HMAC and checkpoint, validates exactly one unanchored record, commits a unique permit identifier in `production_recovery_permits`, then advances the external checkpoint. On crash between these operations the same permit is rejected; a new permit may be required. `run_factory('module:function')` invokes trusted local factory code; it is not safe to accept module paths from IPC clients. This API is opt-in and does not disable legacy modules globally.

## AI-CORE-013 production runtime contract
`production013.load_config(path)` accepts exactly the required trusted configuration fields and rejects non-regular, symlinked, wrong-owner, non-0600 or oversized config. `production013.create_service(path)` requires non-root UID, private directory 0700, socket directory 0710, and private files 0600, verifies all trust anchors before reclaiming a stale socket, and returns `(service, store)`. `production013.run(path)` owns and closes the store after service exit. `AdmissionSupervisor(..., service_gid=...)` optionally sets child group; the prior signature remains compatible. A mismatch or incomplete recovery fails closed. No automatic checkpoint repair.

## AI-CORE-016 contract
`cold_recover(config_path, permit, operator_verified=True) -> (seq, head)` is an offline-only administrative function. Preconditions: exclusive ownership of private directory, no active socket, PREPARED journal, checkpoint at journal old head, signed permit for old head, verified audit chain and independent anchor. No IPC or automatic recovery permitted. A second recovery attempt is rejected when the journal is CLEAN. This is not a cryptographically independent rollback oracle.

## AI-CORE-017
`python -m ai_cognition.production013` exits nonzero with
`LEGACY_PRODUCTION_ENTRYPOINT_DISABLED`. Importing
`ai_cognition.production013.create_service` is supported for legacy offline
callers only, not an endorsed production admission route.

## AI-CORE-019 — Offline recovery concurrency contract
`cold_recover(config_path, permit, operator_verified=True)` retains its signature. It now raises `RecoveryRequired('RECOVERY_ALREADY_IN_PROGRESS')` if another process holds the advisory recovery lock; it does not wait for it. Once the lock is held, it rechecks that no active IPC socket exists. A signed permit remains mandatory and is durably consumed before CLEAN is published. This is advisory locking: untrusted code with the service UID can bypass the lock; the OS security boundary must prevent such code from running. A new recovery attempt after a crash must revalidate every persisted trust component.

## AI-CORE-020 runtime contract
`locking020.acquire_runtime_lock(private)` returns a file descriptor with an exclusive nonblocking flock. The caller MUST release it via `release_runtime_lock(fd)` in a finally block. The lock filename remains `recovery016.lock` for cold-recovery compatibility. `production015.run` holds the lock across factory creation and serve. `production016.cold_recover` uses the same lock. This is local advisory filesystem coordination, not an OS mandatory access control mechanism.
