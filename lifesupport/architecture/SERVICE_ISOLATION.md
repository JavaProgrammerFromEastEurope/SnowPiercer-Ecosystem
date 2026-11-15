# LIFE-CORE-012 — Unix IPC service isolation

The service is a read-only offline logical lifecycle process. It opens and replays the existing SQLite journal, exposing `health` and `snapshot` only. No physical equipment commands and no remote write operations are supported. The existing modules are unchanged.

## Security boundaries

Linux `SO_PEERCRED` authenticates the connecting UID; only the server UID is accepted. The socket directory must be owner-owned `0700`; the socket and SQLite file must be `0600`. The service refuses a pre-existing socket path rather than unlinking an attacker-controlled entry. The client rejects symlinks and checks socket owner and mode before connecting. These checks are not an atomic defense against same-UID path substitution.

This is NOT mandatory isolation for a same-UID legacy writer: such a writer can still access SQLite directly. Production deployment requires a dedicated service UID, separate unprivileged client UIDs, restricted filesystem access, and an audited supervisor. `SO_PEERCRED` is Linux-only. No TLS, privilege sandbox, seccomp, systemd unit, or power-loss durability qualification is provided.

After SIGKILL the socket inode may remain. The operator/supervisor must validate the dead process and safely remove that inode before restart. Automatic cleanup is intentionally not performed. Reopening the SQLite journal replays committed events; no automatic resolution of incomplete external anchors is performed.
