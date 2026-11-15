# Preliminary Safety Analysis — LIFE-CORE-018
| Hazard | Mitigation | Residual risk |
|---|---|---|
| Receipt deletion/tamper | Authenticated external snapshot | Key compromise |
| Receipt points to wrong event | Event-reference verification | Privileged database rewrite |
| Crash after COMMIT | Fail-closed mismatch | Operator reconciliation needed |
| Anchor rollback | Independent anchor protection assumed | Joint DB+anchor rollback undetectable |
| Anchor symlink substitution | lstat and rejection | Directory substitution race |
| False reconciliation | Explicit approval | Approval not cryptographically attested |
| Legacy write bypass | Documented opt-in boundary | Mandatory integration not yet implemented |
| Power failure | fsync file and parent directory | Filesystem and storage hardware not qualified |

NO-GO for physical life-support actuation; no certified safety case.
