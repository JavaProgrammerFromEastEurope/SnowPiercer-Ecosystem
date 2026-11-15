# LIFE-CORE-015 preliminary hazard analysis

| Hazard | Mitigation | Residual limitation |
|---|---|---|
| Fake socket server | Connected SO_PEERCRED UID/PID check | Privileged spoofing/compromise not addressed |
| Stale socket | inode-checked cleanup with supervisor lock | TOCTOU against same UID remains |
| Concurrent supervisor | flock | Privileged lock replacement remains |
| Child crash | bounded restart loop | Supervisor crash not recovered |
| Unauthorized client | SO_PEERCRED allowlist | Client UID compromise remains |
| Resource exhaustion | frame cap, timeout, serial accept | No per-UID rate limiting or quotas |
| SQLite crash | rollback test and integrity_check | No power-loss testing |
| Unauthorized writes | No write IPC op | Same-UID/root direct DB modification possible |

Safety classification: software prototype; NO-GO for physical life-support actuation.
