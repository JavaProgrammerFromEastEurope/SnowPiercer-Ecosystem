# LIFE-CORE-011 preliminary hazard assessment

| Hazard | Mitigation | Residual risk |
|---|---|---|
| Legacy writer appends during rotation | SQLite writer lock + admission UDF checks persistent fence | Alternate APIs and privileged schema changes bypass this check |
| Crash after new anchor before cleanup | Pending intent and fence remain, reopening fails closed | Manual recovery required; potential service outage |
| Crash after fence creation before intent | Orphan fence blocks writes | Manual operator intervention needed |
| Fence deleted by privileged actor | None in this stage | High; no independent authority or file access control validation |
| Power failure loses metadata ordering | fsync file and parent directory where available | Not proven for all filesystems and storage controllers |
| Incorrect operator recovery | No automatic cleanup | Operational procedure and dual authorization not implemented |

**Safety status: NO-GO for physical life-support control.**
