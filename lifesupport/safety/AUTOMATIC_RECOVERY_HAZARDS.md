# Preliminary hazard analysis — LIFE-CORE-013

| Hazard | Mitigation | Residual risk |
|---|---|---|
| Stale socket hijack | ownership/mode/inode checks, exclusive supervisor lock | TOCTOU against same UID, filesystem adversary |
| Duplicate service | advisory flock | same-UID malicious bypass, external supervisors |
| SQLite corruption | replay and integrity checks on startup | physical storage/power-loss behavior untested |
| Unauthorized direct DB write | dedicated UID and private directory policy | root and same-UID bypass, policy not an OS sandbox |
| Endless restart storm | fail closed on readiness timeout | child may crash repeatedly after readiness |
| Recovery after key rotation | no automatic reconciliation | external anchors can diverge |
| Unavailable cross-UID IPC | owner-only directory and socket | cross-UID clients intentionally denied |

Safety status: NO-GO for physical life-support control.
