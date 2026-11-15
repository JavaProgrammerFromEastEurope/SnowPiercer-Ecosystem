# RAIL-TRUST-015 — Independent Monotonic Root & Verified MAC Confinement

Cumulative RailSystem **v0.25** from the exact RailSystem v0.24 artifact. **PARTIAL / BLOCKED / NO-GO**. This package is a laboratory *software release* evidence artifact. It grants **no physical rail command, traction, braking, routing or movement authority**.

## 1. Requirements and traceability

| Requirement | Contract | Evidence | Status |
|---|---|---|---|
| R015-01 | Preserve v0.24 sources/library import surface and all existing tests | cumulative source-hash comparison, full regressions | verified for tested surface |
| R015-02 | Cryptographically verify external root response: unique challenge, pinned Ed25519 key, root ID, key ID, signed sequence and nonce | `monotonic_root.verify_root_quote`, root protocol negative tests | protocol PASS |
| R015-03 | Reject replay, stale challenge, stale sequence, revoked/unpinned signer, malformed/downgraded quote | `test_monotonic_root_015.py` | PASS for protocol |
| R015-04 | Never equate a valid signed quote with independently protected/monotonic storage | `production_authorized=False`, `require_independent_root()` rejects | PASS fail-closed |
| R015-05 | Verify enforced same-UID legacy write denial by an independently administered MAC/LSM policy | `assess_os_management()` diagnostics | NOT MET: no verified MAC policy |
| R015-06 | Make every shipped executable production release/write/recovery entrypoint fail closed without independent MAC/root evidence | `release_cli`, `trust_cli`, `write_authority.main`, `service_runtime.main` | PASS for these entrypoints |
| R015-07 | Independently supervise recovery after SIGKILL (do not auto-delete stale sockets) | existing v0.24 OS-level tests, PID 1 probe | NOT MET: supervisor lifecycle not installed |
| R015-08 | Four real UIDs and cross-UID denial, concurrent CAS, SIGTERM, SIGKILL around local SQLite COMMIT | cumulative tests RAIL-TRUST-011 to 014 | PASS locally; NOT a production claim |
| R015-09 | Full-disk snapshot/host-root rollback resistance and independent durable permits | no hardware/HSM/remote independently managed root installed | NOT MET |
| R015-10 | Complete fault matrix across production root, phase journal, IPC, source file/sockets, credentials and restarts | local tests + persisted matrix | NOT MET |
| R015-11 | Record all PASS/FAIL, stdout/stderr, timeouts, exit codes, SHA-256, archive | `evidence/RAIL-TRUST-015*`, separate external reports and manifest | implemented |

## 2. Architecture and trust boundaries

```
client UID --[kernel SO_PEERCRED / UDS]--> write UID --[DB, phase, admission.lock]--> local service SQLite
                                                |  X fail-closed production gate
                                                +-- authenticated UDS --> witness UID [lab SQLite]
                                                +-- authenticated UDS --> recovery UID [lab permits]

Required but NOT deployed for production:
  [independent monotonic HSM/TPM/remote root + independent signer enrollment]
  [independent durable non-rollbackable consumed-permit state]
  [MAC/LSM executable/subject confinement denying arbitrary same-UID Python]
  [independent service manager + crash reconciliation]
  [audited recovery and physical safety assurance]
```

An **OS DAC file owner** is not an executable identity. Another process with the service's UID can import the previous library and directly change service-owned files. Merely running separate service UIDs or checking `SO_PEERCRED` does not fix this same-UID bypass. Existing library APIs remain importable for compatibility. To close the bypass without breaking them, an operator must enforce an independently installed SELinux/AppArmor/other MAC policy, prove subject transitions and protected path permissions, and prevent running unconfined same-UID executables. The current runtime provides no such proof; production gate denies all attempts. The first-party example systemd units are **not installed**, and PID 1 is not systemd.

## 3. Cryptographic root-quote contract

`monotonic_root.new_challenge()` returns a 256-bit one-use unpredictable hex token. An external independently enrolled signer would return a canonical-JSON Ed25519 signature over exactly:

```
{ "domain":"snowpiercer.railsystem.external-root.quote.v1", "schema_version":1,
  "key_id":"device-01", "root_id":"remote-hsm-1", "challenge":"<64 lowercase hex>",
  "sequence": 42, "nonce":"bound-to-state" }
```

`verify_root_quote(quote, public_key=<base64 32-byte key>, key_id, root_id, challenge, minimum_sequence, revoked_keys=...)` validates the fixed schema, pinned signer identity, challenge equality, monotonic lower bound and Ed25519 signature. On success it returns `CRYPTOGRAPHIC_PROTOCOL_ONLY` with `independent_custody_verified=False`, `production_authorized=False` and `physical_operations_authorized=False`. These explicit false values prevent mistaking the verifier for an independent attestation service. **It does not claim key enrollment/custody, hardware security, anti-rollback persistence, monotonic operations, or operator approval.** `require_independent_root()` is an intentional non-bypassable fail-closed integration placeholder until independently audited provisioning is provided.

An attacker with a signer key or an entire rolled-back image can produce a valid quote. Thus a valid signature, challenge, and locally stored sequence floor are necessary input hygiene but **not sufficient** to demonstrate external monotonicity. No signer with independently protected custody is shipped.

## 4. Production admission and safe failure

- `release_cli.main` (and compatibility alias `trust_cli`) invokes `require_production_isolation()` before calling the legacy `unified_admission.admit()` when the CLI has otherwise complete parameters. Missing parameters already return `BLOCKED`. This guard cannot be overridden through environment variables or substituted `assess_os_management()` diagnostics.
- `write_authority.main` and `service_runtime.main` already invoke the same mandatory guard, preventing these executables from launching a production socket in this environment.
- Library APIs `unified_admission.admit()`, `recover()`, `release_gate.evaluate()`, `ProductionWriteAuthority.start()`, etc. are deliberately retained. Code with same service UID and direct filesystem access remains an **OPEN BYPASS** for a hostile insider. Production deployment therefore must not be authorized on the basis of the CLI guards alone.
- Any missing attestation, ambiguous remote CAS reply, stale socket, PREPARED state, revoked key, UID/credential mismatch, or missing independent provider must result in deny/hold. Denial is a safety feature; it is not proof of complete enforcement against privileged attackers.

## 5. OS proof and incident response

`os_managed_fencing.assess_os_management()` only records `pid1`, `/proc/self/attr/current`, LSM inventory (if accessible), `NoNewPrivs`, seccomp and capability indicators. **No self-reported process label can establish correct subject/object enforcement.** The routine deliberately never returns a positive isolation proof, even when fed synthetic `systemd` and enforcing-label strings in tests. `require_production_isolation()` reads the standard kernel paths and denies regardless of test-provided diagnostics. Service-manager readiness, MAC policies, independent remote roots and durable permits need an external verification process and an operator-signed deployment baseline, which are outside this artifact.

A crash after witness CAS may produce an ambiguous reply while SQLite remains PREPARED. Preserve the fence and require separately authenticated reconciliation. Never infer a successful commit from timeout, auto-consume a recovery permit, auto-unlink a crash-stale socket or silently reset an anchor. A local snapshot rollback including SQLite and the local lab witness/ledger cannot be detected reliably by these local files.

## 6. Verification and limitations

Full strict cumulative command from source root:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS='error::ResourceWarning,error::DeprecationWarning' PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_*.py' -v
```

Run three times after final edits. Save all stdout/stderr, process return codes, duration, timeout flag, stage test coverage and source/ZIP SHA-256. The older local fault matrix contains genuine process SIGKILL tests around SQLite and IPC, but is **not** exhaustive of all kernel write boundaries nor a power-failure/host-rollback proof. New tests verify root-message semantics and fail-closed startup; they do not create an operational trust root. Host root, service UID code, LSM configuration admins, and storage administrators are out-of-scope adversaries until externally tested and constrained. Release gate: **BLOCKED**. Physical system: **NO-GO**.
