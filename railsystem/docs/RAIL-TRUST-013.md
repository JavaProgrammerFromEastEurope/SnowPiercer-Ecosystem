# RAIL-TRUST-013 — Independent Authority Deployment & Mandatory Production Write Fencing

Version: RailSystem v0.23 (one cumulative functional Stage). Safety state: **PARTIAL / BLOCKED / NO-GO**.

## Baseline and compatibility

Source baseline: the exact contents of `RailSystem_v0.22_RAIL-TRUST-012.zip`.
Existing Python library functions and tests from RAIL-ARCH-001 through RAIL-TRUST-012 are retained. The new path is an opt-in, stricter production software-release **write authority**, not a train-control interface and not a safety certification.

## Requirements

| ID | Requirement | Status |
|---|---|---|
| R013-01 | Dedicated non-root service UID owns release state (`0700`) | Linux integration PASS |
| R013-02 | Four separate UID roles: client, service/write authority, witness, recovery/permit authority | Linux integration PASS |
| R013-03 | Authenticated peer UID and bounded, fixed request grammar | Linux integration PASS |
| R013-04 | No IPC publication without independently authenticated witness and permit ledger endpoints | Fail-closed test PASS; providers are volatile test doubles |
| R013-05 | Shared lifecycle lock for preflight, admission and local commit | Implemented in write endpoint; local tests PASS |
| R013-06 | No direct client write to service state or protected credential files | Linux DAC negative test PASS |
| R013-07 | Only ADMIT accepted; no client-defined file paths/trust policy | Linux negative tests PASS |
| R013-08 | SIGTERM orderly cleanup and SIGKILL leaves a fenced stale socket | Linux tests PASS |
| R013-09 | Independent persistent anti-rollback CAS witness | NOT DEPLOYED; production BLOCKED |
| R013-10 | Independent, durable and rollback-resistant permit authority | NOT DEPLOYED; production BLOCKED |
| R013-11 | End-to-end cross-UID production ADMIT with independently approved signed release | NOT VERIFIED |
| R013-12 | Deny every legacy production write including same-service-UID Python | NOT MET; OS DAC cannot prevent owner/root bypass |
| R013-13 | Independently managed OS service restart and four UID daemon supervision | UNIT EXAMPLE ONLY, NOT DEPLOYED |
| R013-14 | Exhaustive SIGKILL/SIGTERM at SQLite/CAS/permit/IPC boundaries against real durable providers | NOT MET; earlier volatile-provider fault tests remain in cumulative suite |

## Architecture

```
Client UID --(group-only Unix socket + SO_PEERCRED)--> Write authority / service UID
                                                        | common admission.lock
                                                        | SQLite PREPARED/IDLE
                                                        | local anchor
                                                        +--> witness UID [authenticated Unix CAS]
                                                        +--> recovery UID [authenticated Unix permit readiness]

Recovery broker / service UID <--(SO_PEERCRED)--------- Client UID
                                                        | independent permit consume
                                                        | witness read/CAS reconciliation
```

`ProductionWriteAuthority.start()` requires a valid four-role configuration and authenticated provider responses. Under `admission.lock` it requires SQLite to agree with local/external anchor before publishing `write-v013.sock`. An existing socket, even if left by a killed process, blocks startup rather than being blindly removed. `handle_one()` verifies socket inode, OS peer credentials, only `ADMIT\n`, provider readiness and recovery fence *again* under the same lock, and then invokes `unified_admission.admit(..., _lock_held=True)`. This avoids recursive flock and prevents a concurrent offline recovery commit from crossing the lock. All inputs are service-controlled protected files, never supplied by the client. `close()` only removes an inode it owns.

## API and service contracts

`ProductionWriteAuthority(config, *, root, baseline_file, attestation_file, trust_file)` creates a library object but does not start or elevate a process. `start()`, `handle_one()` and `close()` manage the endpoint; `serve()` handles SIGTERM and serves until shutdown. CLI: `python -m railsystem.write_authority --config ... --root ... --baseline ... --attestation ... --trust ...`. Command response is JSON `{"status":"BLOCKED"}` or a software release gate response. No client-selected artifact paths or recovery permits. Invalid or ambiguous remote replies block; there is no bypass to legacy release gates.

The external witness protocol is `read()->(sequence,nonce)` and `advance(old,new)->bool` via `UnixAnchorClient`; independent permit service uses `ready` and `consume` via `UnixPermitLedgerClient`. `SO_PEERCRED` proves process identity but not provider integrity, counter durability, monotonicity across restored snapshots, or independent custody. Production services must provide these properties out of band. The existing test providers explicitly do NOT.

All artifact credential files must be service-owned `0400` or `0600` and in a service-owned non-group-accessible directory. State directory `0700`, IPC directory `0750` with dedicated transport GID, socket `0660`; root is not an allowed application UID. Client access to state files fails by OS DAC. The systemd file is a **template**, and the present environment runs `supervisord` as PID 1, not systemd.

## Crash-consistency and safety argument

The pre-existing phase journal persists `PREPARED` before remote CAS; the external authority can advance without local final SQLite commit. In that state recovery is mandatory and write startup blocks. In recovery, external permit is consumed before local commit; crash after consumption burns the permit and requires a new signed permit. Local `flock` only serializes writers cooperating on the same state directory. No two-phase commit with a distributed independent storage system is claimed; ambiguity is resolved by denying rather than granting admission.

Threat inventory: forged UID, unauthorized IPC verb, socket replacement, file symlink, concurrent startup, witness/permit outage, SIGTERM, SIGKILL, SQLite rollback, simultaneous rollback of witness/permit files, privileged host/root attacker, same-service-UID arbitrary Python, incomplete rollback proof. Positive tests cover the first seven; local kill tests cover portions of the next three. Full host rollback, privilege-separated durable services, tamper-resistant witness and all same-UID code are NOT proven and constitute open safety hazards.

## Legacy entrypoint audit

Library functions `trusted_admission.admit`, `anchored_admission.admit_anchored`, `anchored_admission.recover`, `production_fencing.recover_with_attestation`, `unified_admission.admit`, `unified_admission.recover`, and `anchored_admission.initialize` remain public/importable for compatibility. `release_cli.main` still provides legacy software CLI semantics (without a provider it fails closed). The operating system can deny non-service UID access to the production state directory, but cannot distinguish unauthorized Python code using the service UID from the intended write authority. **Therefore full OS-enforced production bypass elimination is not achieved.** See `evidence/RAIL-TRUST-013_legacy_audit.json`.

## Tests, evidence and release gates

A real Linux root-capable test harness forks four processes under UIDs 62581–62584 and transport GID 62580, and tests peer-credential rejection, client state denial, provider loss, concurrent startup, socket substitution, SIGTERM cleanup, SIGKILL during request, rollback fence (`PREPARED`), bad owner/modes and credential symlinks. These UIDs are ephemeral numeric test UIDs, not independently administered system accounts. Tests are only **nonproduction simulations**, and their mock witness/permit ledger loses state on provider restart.

Run strict suite: `PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS='error::ResourceWarning,error::DeprecationWarning' PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_*.py' -v`.

Three complete runs, stdout, stderr, exit codes and SHA-256 inventory are included in `evidence/`. Failed trials from earlier stages remain preserved in cumulative evidence. Stage does not authorize live railway movement. Release admission **BLOCKED**; physical operation **NO-GO** until independent durability, OS service manager integration, same-UID legacy isolation and end-to-end tests are independently demonstrated.
