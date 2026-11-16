# ISLAND-GEO-020 — Boundary consolidation (experimental)

Client UID → unprivileged facade UID → broker UID → witness UID.

The broker owns the production SQLite ledger; the facade has no ledger path. The broker checks SO_PEERCRED of the facade and pins the witness peer UID. A state-bound permit is consumed before recovery. Startup uses an exclusive broker lifetime lock. Previous library APIs remain importable.

## Mandatory OS provisioning (not provided by the Python library)

Create four distinct non-root UIDs. Provision a broker-private directory (0700), an authority-private directory (0700), and a root-controlled sticky IPC namespace with socket permissions/groups configured for intended peers. Deny service/client UID read and write to broker ledger, journal, lock and checkpoint files. No service process may run as broker UID. Independently verify negative access probes and policy across all aliases and mount namespaces.

## Unresolved safety-critical properties

A compromised service can impersonate a client *to the broker* because the broker authenticates only the service UID; the facade authenticates clients locally. No cryptographic end-to-end client attestation is carried through. A process with broker UID can still import legacy APIs. The witness is a writable SQLite database and has no hardware-backed anti-rollback. The Python runtime is not a mandatory OS access-control policy. Therefore production security is BLOCKED/NO-GO.

The crash instrumentation inherited from previous stages exists, but no exhaustive production broker SIGKILL matrix was executed in this Stage. Physical construction and operations remain BLOCKED/NO-GO.
