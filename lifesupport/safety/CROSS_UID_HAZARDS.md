# LIFE-CORE-014 preliminary safety assessment

| Hazard | Mitigation | Residual risk |
|---|---|---|
| Same-UID DB bypass | Dedicated service UID, private storage directory | Privileged or service-UID attacker can bypass |
| Unauthorized IPC | Kernel SO_PEERCRED allowlist | Root and compromised service process |
| Socket substitution | Refuse occupied socket at startup | Client does not authenticate server identity |
| DoS via accessible socket | Bounded frames, per-connection timeout | Sequential request handling and unlimited connection attempts |
| Torn transaction | SQLite COMMIT atomicity, SIGKILL fault tests | Power failure and storage firmware behavior untested |
| Unchecked production transition | All remote mutations disabled | No production write interface available |
| Service crash | Existing legacy supervisor only | Opt-in service not auto-restarted |

Status: NO-GO for safety-critical or physical life-support deployment.
