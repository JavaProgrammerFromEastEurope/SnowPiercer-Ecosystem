# ISLAND-GEO-022 — Independent Monotonic Witness Root & OS-MAC Legacy Confinement

## 1. Cumulative preservation

Island v0.23.0 retains all previous Stage modules, CLI entrypoints, tests, requirements, safety artefacts and evidence from v0.22.0. Existing `AttestedWriteBroker` now exposes an overridable `_authority_client` factory; the default remains unchanged. `SplitAttestedWriteBroker` overrides it to forward `read/cas` to witness and `consume` to recovery authority without changing prior library call signatures.

## 2. Six-principal architecture

| Principal | Privileges | IPC permissions | Storage |
|---|---|---|---|
| Client | nonroot UID 25001 in tests | facade, issue only | client Ed25519 private key |
| Facade | nonroot UID 25002 | broker, client | no ledger file access |
| Write broker | nonroot UID 25003 | witness CAS, permit consume | broker SQLite/phase/nonce and client public key |
| Witness | nonroot UID 25004 | root CAS, broker/permit read | witness SQLite, root verifier public key |
| Recovery authority | nonroot UID 25005 | witness read, issue to client, consume from broker | separate permit SQLite |
| Monotonic root fixture | nonroot UID 25006 | witness only | separate signed SQLite and Ed25519 private key |

`SplitWitnessServer`, `SplitPermitServer`, `SoftwareRootServer`, `RootClient` provide strict peer UID pinning. Production root provider remains unimplemented, meaning strict broker cannot start. The software root in the lab **can be rolled back**, including a rollback of all databases and signing keys together.

## 3. Root protocol and crash semantics

Every witness `read` requires a fresh 128-bit challenge and signature-verification of the root head `(sequence,digest)`. A witness CAS checks current root head before local mutation, commits witness CAS, then sends root CAS, then rechecks the root. If the witness process is killed between the commits, divergence is recognized and **all new reads/admissions fail closed**; no automatic forward-repair occurs. This sacrifices availability. It is not a distributed atomic commit and it is not a proof of power-loss durability. Broker startup still requires a direct-client-issued, single-use state-bound permit before reconciliation or exposing IPC.

## 4. Mandatory production gate and OS limitations

`StrictSplitBroker` calls `require_production_security()` **before startup lease, SQLite, permit or socket**. `HostSecurityEvidence` derives observations from kernel paths, euid and PID1. The verified hardware monotonic root, loaded MAC policy coverage for same-UID broker arbitrary code, and independent lifecycle proof are explicitly false until a trusted verifier exists. Environment flags do not override them. In the current container there is no `/dev/tpm*`, no observed enforcing LSM, PID1 is `supervisord`; therefore fail-closed is the only supported production result.

`SplitAttestedWriteBroker` and `SoftwareRootServer` are clearly marked lab-only alternatives. Their existence is **not** OS-level removal of same-UID legacy production bypass. Since broker needs to read/execute Python and write SQLite, DAC cannot distinguish a legitimate broker operation from legacy Python code executed under the broker UID. The required independently loaded MAC policy and verified pre-exec service manager are not installed. Production security must remain NO-GO.

## 5. Test coverage and limitations

`tests/test_stage023.py` runs strict denial and signed protocol unit tests. `tests/stage023_sixuid.py` drives six real unprivileged UID processes on a disposable Linux test host with root controller, negative file access, peer identity, replay, startup lease, signed admissions, broker SIGKILL and genesis rollback. Each check reports PASS/FAIL and attempted crashes, retaining subprocess streams and exit codes. The root controller can impersonate all roles, so this is **not independently trusted hardware evidence**.

Unresolved: certified monotonic resource, loaded OS-MAC policy against same-UID code, immutable service manager, exhaustive witness/permit/root crash interleavings, independent power-loss/fdatasync testing, complete TOCTOU socket and file mutation coverage. NO-GO applies to construction, geological design, permitting and operation.
