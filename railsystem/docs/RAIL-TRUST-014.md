# RAIL-TRUST-014 — OS-Managed Authority Isolation & Durable Witness Crash Verification

RailSystem **v0.24**, cumulative from the exact `RailSystem_v0.23_RAIL-TRUST-013.zip` source. Safety verdict: **PARTIAL / BLOCKED / NO-GO**. Software release admission only: no railway movement authority and no operational certification.

## 1. Scope and safety decision

The prior source provided peer-credentialled four-UID IPC clients but only **volatile test doubles** for witness/permit storage. This Stage implements **local durable laboratory authorities** with separated Linux UIDs, SQLite `synchronous=FULL`, `BEGIN IMMEDIATE`, and authenticated `SO_PEERCRED` requests. Their state remains after a process SIGKILL and managed laboratory restart, with evidence differentiating a kill before SQLite COMMIT versus after COMMIT.

**These are NOT independent production monotonic anchors:** root, the authority UID, storage administrator, or whole-disk snapshot restore can replace their SQLite state, including sequence and consumed permits. No TPM/HSM/remote independent rollback-resistant root is connected. No MAC/LSM policy restricting same-UID Python/legacy APIs is independently attested. Therefore software production CLI entrypoints for write and recovery are explicitly gated by `require_production_isolation()`, which denies until such independent OS proof is implemented and audited. It intentionally has no environment-variable shortcut or `--unsafe-production` bypass. Previous Python library functions remain importable.

## 2. Requirements and traceability

| ID | Requirement | Evidence/status |
|---|---|---|
| R014-01 | Retain all v0.23 library APIs/source and cumulative tests | Full cumulative regression; source archive comparison |
| R014-02 | Four distinct real non-root UIDs (client, write service, witness, recovery/permits) | `test_isolated_authorities_014.py`; PASS Linux UID fork/drop |
| R014-03 | Independently owned local witness and permit files, with OS-DAC denial across UID | `test_client_cannot_read_witness_and_permit_databases`; PASS |
| R014-04 | Explicit provision, NO implicit state reset, reject missing/corrupt/symlink state | Negative tests; PASS for tested conditions |
| R014-05 | Monotonic CAS / permit consume via SQLite FULL synchronous atomic commit | CAS/consume and SIGKILL before/after commit tests; PASS for local process crashes |
| R014-06 | One-use recovery permit survives provider process restart | Durable recovery tests; PASS locally |
| R014-07 | Peer UID/GID and Unix-socket path identity authentication with bounded frames | Four-UID IPC tests, prior `provider_ipc.py`; PASS locally |
| R014-08 | Concurrent CAS must serialize / exactly one competing winner | Two concurrent real UID-service callers; PASS |
| R014-09 | SIGTERM cleanup, SIGKILL stale socket blocks unsafe automatic restart | Tests; PASS; manual **test-only** explicit reclamation |
| R014-10 | End-to-end IPC authority -> separate durable UID-backed services, bad attestations fail closed | Integration test; PASS for negative release, not positive certified admission |
| R014-11 | Mandatory OS MAC confinement of all same-service-UID legacy writes | NOT MET; `require_production_isolation` enforces BLOCKED |
| R014-12 | Independently protected monotonic root resistant to host-wide rollback | NOT MET; local SQLite is rollbackable |
| R014-13 | Actual systemd/supervisor managed automatic safe restart after SIGKILL | NOT MET; PID 1 is not systemd; no independent manager deployed |
| R014-14 | Full verified fault-injection matrix at all SQLite/phase/IPC boundaries under independent production authorities | NOT MET; existing cumulative local kill tests + new SQLite provider kill points only |
| R014-15 | No live railway actuation or safety claim | Maintained: BLOCKED / NO-GO |

## 3. Implementation and API contracts

- `railsystem.isolated_authorities.LocalDurableAuthority(kind, state_dir, ipc_dir, transport_gid, service_uid)` is a **lab-only** local provider backend, not a production authority. Its constructor requires kind `anchor` or `permit` and a UID different from the provider's UID. `provision()` succeeds only when its `0700` private directory is empty of prior state. It never resets an existing database. `start()` refuses a stale or replaced socket. `handle_one()` authenticates the **client's actual Linux UID** through `SO_PEERCRED` and validates the fixed provider domain/verb/field set. `serve()` handles SIGTERM for controlled clean shutdown; SIGKILL leaves a stale socket and cannot auto-reopen.
- Database records: `witness(id=1,sequence>=0,nonce)` and `permits(digest PRIMARY KEY, sequence, action)`. `advance(expected,next)` checks the current tuple and commits only increasing sequence. `consume` records a digest only once. `read`/`ready` are queries; RPC replies use the existing `provider_ipc.py` schema, retaining client API compatibility. `BEGIN IMMEDIATE` serializes transactions for that local database; `PRAGMA journal_mode=DELETE` and `PRAGMA synchronous=FULL` control local disk persistence. Cross-host atomicity, fsync guarantees on all hardware, and rollback detection are NOT claimed.
- Operator/test CLI `python -m railsystem.isolated_authorities --kind anchor|permit --state-dir ... --ipc-dir ... --transport-gid ... --service-uid ... --provision` or `--test-only-serve`. A **new separate directory and UID** is required for each role. This CLI is intentionally test-only; the explicit `--test-only-serve` spelling is not an assurance of production trust.
- `railsystem.os_managed_fencing.assess_os_management()` reports diagnostic PID 1 and MAC label but **never** returns authorization. `require_production_isolation()` rejects every unproven deployment. `write_authority.main()` and `service_runtime.main()` now invoke it; existing `ProductionWriteAuthority` and recovery library APIs remain unchanged for compatibility with prior laboratory callers. This is fail-closed, **not** proof that arbitrary same-UID Python has been eliminated.
- `railsystem.verification.STAGE_TESTS` includes RAIL-TRUST-014; the source SHA-256 manifest includes the new module/test/doc and deployment requirements artifact.

## 4. OS-managed deployment architecture (NOT ACTIVATED)

```text
client UID ------ Unix socket, SO_PEERCRED ------> service/write UID
                                                     | strict production gate -> BLOCKED
                                                     | admission.lock, SQLite PREPARED
                                                     +--- Unix RPC ---> witness UID [local SQLite lab ONLY]
                                                     +--- Unix RPC ---> recovery UID [local SQLite lab ONLY]

Required for real production but MISSING:
  (a) independently certified monotonic witness and permit custody,
  (b) enforceable LSM/MAC policy for same-UID Python and legacy paths,
  (c) audited dedicated service manager restart/reconciliation protocol,
  (d) proof of end-to-end crash and rollback resistance.
```

The earlier `systemd/*.service.example` files remain uninstalled; they are **NOT** evidence of a working service manager. A deployment must forbid client or service UID writes to independently owned witness and permits and must prevent arbitrary binaries with the service UID from opening production state directly (requires independently enforced MAC/service split, not merely Unix DAC). The current environment does not supply that authority boundary. See machine-readable `deployment/RAIL-TRUST-014_os_requirements.json`.

## 5. Fault-injection and safety argument

| Fault | Expected behavior |
|---|---|
| Before SQLite witness COMMIT + SIGKILL | Uncommitted CAS rolled back; no successful ACK |
| After witness COMMIT, before reply + SIGKILL | Monotonic value persists locally; client gets ambiguous failure, must re-read |
| Before SQLite permit COMMIT + SIGKILL | No permit consumed; retry possible under new process |
| After permit COMMIT, before reply + SIGKILL | Permit remains burned locally; no successful acknowledgement |
| Concurrent CAS from two clients | Exactly one succeeds from same expected value |
| Provider crash after socket publication | Stale socket remains, fail-closed startup; test cleanup requires explicit operator-like action |
| SIGTERM to provider loop | Socket closed and removed only if inode still belongs to server |
| UID mismatch / replaced socket / symlinked DB / missing state | Reject / no published socket for tested conditions |
| Simultaneous rollback of SQLite state and witness/permit SQLite backends | **NOT PROTECTED**; local lab storage cannot detect it |
| Arbitrary same-service-UID legacy API | **NOT PROTECTED BY DAC**; production CLI gate denies but library remains callable |
| Host crash/power loss, independent service-manager failover, whole-host rollback | **NOT TESTED** |

Additional open hazards: TOCTOU between path `lstat` and SQLite open; no immutable inode-bound DB descriptor, so untrusted same-UID actors can race path replacement. Assumes no compromised authority UID. SQLite FULL only provides contractual durability subject to filesystem/hardware and is NOT a secure anti-rollback root. Peer UID attests process identity, not correctness of a running executable or provider data. SIGKILL tests are targeted, not exhaustive for all intra-SQLite syscalls. No physical brakes/traction/dispatch interfaces exist here.

## 6. Verification, compatibility and artifacts

Strict run from project root:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS='error::ResourceWarning,error::DeprecationWarning' PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_*.py' -v
```

Run three complete times after implementation; store **all** exit codes and stdout/stderr plus earlier failed development trials. Check the `tests/test_*.py` registry and stage-source SHA-256 manifest. Independent external audit has **not** certified the results. The assessed status remains `PARTIAL / BLOCKED / NO-GO`, even if all local regression tests pass.
