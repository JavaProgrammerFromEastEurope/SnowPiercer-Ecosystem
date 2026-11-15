# RAIL-TRUST-010 — Cross-UID Recovery Isolation & Exhaustive Crash-Point Verification

Status: PARTIAL / BLOCKED / NO-GO. The implementation adds a **fail-closed experimental broker**, not a privileged service and not a proof of cross-UID recovery.

## Requirements and contracts

- R010-01: A recovery IPC request MUST authenticate the kernel peer UID; if `SO_PEERCRED` is absent, deny.
- R010-02: A configured immutable UID allowlist MUST be nonempty; unauthorized UIDs MUST be denied.
- R010-03: IPC MUST accept only the exact `RECONCILE\n` verb. Signed permit and recovery key are provisioned out-of-band, not supplied by the client.
- R010-04: Startup MUST fail closed without an independently provisioned anchor. Socket paths MUST be checked for owner, inode and type; pre-existing paths MUST NOT be unlinked.
- R010-05: Existing unified `recover()` MUST remain the sole implementation of reconciliation and replay-permit consumption. Library interfaces MUST remain compatible.
- R010-06: The recovery broker MUST NOT claim to be a privileged cross-UID mediator; file permissions and service-manager policy are external requirements.

## Safety analysis

- **H-01**: Same-host provider and SQLite can both be rolled back. A real independently secured, monotonic CAS provider is required. Current provider contract alone is insufficient.
- **H-02**: Signed permit replay can succeed after rollback of the local permit ledger. Permit consumption requires independent monotonic durable storage.
- **H-03**: Broker socket is mode 0600; this intentionally prevents cross-UID clients unless an explicitly audited service-manager deployment mechanism is provided. Cross-UID E2E NOT TESTED.
- **H-04**: Filesystem inode checks do not prove immunity to all namespace races or privileged attackers.
- **H-05**: Existing `recover()` has a crash window after local anchor update and before SQLite commit; it must be assessed with independent persistent provider.
- **H-06**: Legacy direct library calls remain accessible for compatibility; full production entrypoint inventory is NOT completed.

## Verification evidence

The new tests cover fail-closed startup, real Linux SO_PEERCRED on a local socketpair, invalid UID allowlists, socket-path substitution and rejection of legacy IPC commands. The prior cumulative suite covers selected SIGKILL paths. An exhaustive fault-injection matrix across SQLite, journal, external anchor, IPC, and independent permit store is NOT complete. No hardware anchor or cross-UID privileged broker is provisioned.

Release decision: BLOCKED. Physical railway operation: NO-GO.
