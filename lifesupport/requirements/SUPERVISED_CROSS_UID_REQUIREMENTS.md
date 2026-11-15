# LIFE-CORE-015 requirements

- LS-015-01: Supervisor must run with service-owned IPC directory (0711).
- LS-015-02: Private SQLite directory must be service-owned 0700.
- LS-015-03: Service UID must not be in the client allowlist.
- LS-015-04: Linux SO_PEERCRED must authenticate connected server UID.
- LS-015-05: Optional expected PID must be verified on connected socket.
- LS-015-06: Live sockets must not be removed during recovery.
- LS-015-07: Non-socket and symlink occupants must be rejected.
- LS-015-08: Supervisor must serialize instances with flock.
- LS-015-09: Crashed child must be restarted subject to restart budget.
- LS-015-10: Production writes must remain disabled.
- LS-015-11: IPC frame must be bounded to 65536 bytes.
- LS-015-12: Test SIGKILL before SQLite COMMIT and competing writers.
- LS-015-13: ResourceWarning must be treated as test errors.
- LS-015-14: Do not claim protection against service UID/root or power loss.
