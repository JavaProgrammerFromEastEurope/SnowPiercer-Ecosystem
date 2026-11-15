# LIFE-CORE-015 architecture

`CrossUIDSupervisor` is opt-in, and leaves legacy `ServiceSupervisor` intact. It launches `lifesupport.cross_uid_cli` with an explicit client UID allowlist. `AuthorizedLifecycleService` provides only `health` and `snapshot`. `verified_request` validates kernel `SO_PEERCRED` UID and optional PID **after connecting**. A root/service-UID supervisor receives an unauthorized response from its own child; this response is used solely as a readiness indication after verifying PID/UID, never as permission to read or write.

Private DB directory: service-owned 0700; IPC directory: service-owned 0711; socket 0666 with UID authorization enforced in handler. Supervisor uses a 0600 lock and inode-checked stale socket cleanup. Serial accept loop, 2-second client read timeout, 65536-byte framing, backlog 32; these are bounds, not global DoS protection.

This stage does not drop privileges, change UID, provide production writes, protect against same-UID/root modification, guarantee power-failure atomicity, or supervise the supervisor itself. The Linux root test exercises a root-owned service and UID 65534 client, not a separately provisioned unprivileged service account.
