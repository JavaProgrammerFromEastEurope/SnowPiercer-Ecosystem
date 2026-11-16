# ISLAND-GEO-021 — architecture, contract and safety case

## Scope
Cumulative Island v0.22.0. Existing `island.write_broker` and historical APIs
are retained. New opt-in `island.attested_broker` / `island.attested_runtime`
implements four roles (client 24001, facade 24002, broker 24003 and combined
witness/recovery authority 24004 in the disposable Linux test). Roles are
OS-nonroot and run under distinct real kernel credentials. Combined witness
and permit authority is **not** separately isolated into two users.

## Data/control path
1. An independently provisioned client private Ed25519 key is confined under
   the client UID in mode 0600/0700 storage. Broker has only a pinned public
   key in its own private storage. Root controller provisions both during test.
2. Client signs canonical JSON containing payload hex, random 128-bit nonce,
   protocol/domain tag, its UID and the target broker UID.
3. Facade checks connecting client via SO_PEERCRED and forwards envelope;
   facade may not open the broker ledger and cannot forge client signatures.
4. Broker checks facade UID via SO_PEERCRED and independently verifies the
   signature, signed principal, content and pinned client public key.
5. Broker reserves (burns) signed nonce in its private SQLite using BEGIN
   IMMEDIATE, synchronous=FULL, COMMIT **before** invoking anchored admission.
   Replays are denied. An interrupted request between nonce burn and witness
   CAS may be lost permanently: fail-closed safety over availability.
6. Anchored admission uses phase journal, SQLite accepted chain and independent
   witness CAS, with the previous reconciliation and 13 injected SIGKILL points.
7. On broker startup, authority verifies previously issued direct-client permit
   and current witness head; the permit is one-use; only then does recovery
   execute, followed by socket publication. The token is read from an inherited
   file descriptor, not command arguments.

## Safety limitations and missing guarantees
- Independent irreversible anti-rollback root is **not** provided: the witness
  itself is SQLite, privileged rollback of both stores remains possible.
- There is NO OS MAC/LSM confinement preventing code running as broker UID from
  importing old library APIs and writing the broker-owned SQLite directly.
  POSIX DAC denies client/facade/witness UID access to broker storage only.
- The test root controller can delete/replace every file, assume any UID and
  recover stale sockets. This tests negative access of nonroot principals, not
  resistance to root.
- No physical drive fsync/power-loss injection, service-manager/watchdog lifecycle
  isolation, or complete syscall-level crash exhaustive search.
- Socket inode owner and SO_PEERCRED pinning do not prove race freedom against
  privileged namespace takeover.
- Crypto key rotation, secure provisioning and independent key attestation remain
  subject to separate acceptance tests.

## Production gate
New signed entrypoint rejects legacy unsigned requests; the historical
`WriteBroker` and direct Python `AnchoredAdmission` remain available for
library callers. The OS must enforce the production launch profile so that
these callers cannot touch protected broker files. No such mandatory policy is
installed or proved here. **Production Security = BLOCKED/NO-GO**.
**Physical Construction & Operations = BLOCKED/NO-GO**.

## Evidence methods
Three full strict-warning unittest runs, real four-UID kernel peer and DAC probes,
actual -SIGKILL crash points executed inside the broker, independent startup
permits, genesis rollback and selected tampering. Tests executed by privileged
Linux orchestrator in disposable directories. Evidence provides executed/
not-verified distinctions, exact exit codes and per-process stdout/stderr.
