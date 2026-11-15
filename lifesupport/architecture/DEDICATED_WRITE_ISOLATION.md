# LIFE-CORE-016 — Dedicated Service Identity & Mandatory Write Isolation

The optional `ProductionWriteService` is a Linux AF_UNIX stream server run as a dedicated **non-root** UID. Client identity is obtained from kernel `SO_PEERCRED`, never supplied by JSON. The server owns a 0700 private SQLite directory and 0600 SQLite/WAL/SHM files. The socket directory is service-owned 0711 and the socket is 0666; admission is enforced by peer credentials, not the socket mode. No actuator commands are implemented.

## Provisioning and trust boundary

An administrator must provision a separate service UID and client UID(s), protected SQLite v2 database, and filesystem ownership before starting the service. Database migration is offline and explicit. The write service refuses unprotected or v1 databases. It uses existing `HardenedLifecycle` admission guards and a server-issued short-lived fence for every request. The client cannot choose the event actor or fence token. Existing read-only services and legacy offline APIs remain unchanged.

## Crash and replay

SQLite WAL is reopened after service restart and event history is replayed. A stale socket must be reconciled by a trusted supervisor. A process killed after acquiring a lease may leave an unexpired lease (10 s), so immediate restart can temporarily reject writes. The client cannot determine whether a timed-out request committed: callers must reconcile via `snapshot` or journal inspection before retrying. There is no end-to-end exactly-once guarantee. Disk-full, power failure, compromised service UID, root, symlink races outside the checked paths, and unsafe provisioning are not fully addressed.

## Remaining mandatory isolation gaps

Legacy APIs are blocked by kernel DAC only for *different* unprivileged UIDs. Root and the service UID can still bypass the IPC. The write service is opt-in; the prior service classes are retained for compatibility. Existing supervisor can be configured with a different CLI module, but this Stage does not claim tested autonomous write-service recovery under a dedicated UID. Do not connect to physical life-support equipment (NO-GO).
