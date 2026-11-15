# LIFE-CORE-014 requirements

- LS-014-01: Opt-in Linux SO_PEERCRED authorization must reject unknown client UID.
- LS-014-02: The service must deny all IPC state-changing operations.
- LS-014-03: Client UID must differ from service UID.
- LS-014-04: Storage directory must be service-owned and mode 0700.
- LS-014-05: SQLite and sidecar files, when present, must be service-owned and mode 0600.
- LS-014-06: Socket directory must be service-owned and mode 0711.
- LS-014-07: The IPC socket must not be replaced or silently unlinked at startup.
- LS-014-08: Legacy owner-only service behavior must remain compatible.
- LS-014-09: Process death before SQLite COMMIT must not expose an uncommitted event.
- LS-014-10: Process death after SQLite COMMIT must preserve committed data on restart.
- LS-014-11: Cross-UID IPC must be verified with actual OS credentials when supported.
- LS-014-12: ResourceWarning must be treated as an error in regression runs.
