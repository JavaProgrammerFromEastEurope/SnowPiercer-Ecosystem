# LIFE-CORE-012 safety analysis (preliminary)

| Hazard | Mitigation in this stage | Residual risk |
|---|---|---|
| Cross-UID unauthorized IPC | SO_PEERCRED and 0700 directory | Linux-specific; no remote clients |
| Socket path spoofing | Reject pre-existing path and symlinks | Same-UID race remains |
| Direct SQLite write bypass | Filesystem permissions 0600 | Same-UID and privileged writers remain capable |
| Crash leaves stale socket | Fail closed; manual validated cleanup | No automated recovery supervisor |
| SQLite journal corruption | Replay on read and fail on exception | No independent integrity root here |
| DoS from slow clients | Per-client timeout | Serial server and queue exhaustion possible |
| Accidental physical control | No write or equipment control IPC | Future interfaces require separate safety case |

Safety disposition: NO-GO for physical or production life-support control.
