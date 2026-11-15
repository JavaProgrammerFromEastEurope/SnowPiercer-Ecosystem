# LIFE-CORE-016 — Preliminary hazard analysis

| Hazard | Consequence | Mitigation / residual risk |
|---|---|---|
| Privileged bypass | Unauthorized journal changes | DAC only excludes different unprivileged UIDs; root/service UID remain trusted |
| Client identity spoofing | Unauthorized transitions | SO_PEERCRED kernel UID check; no JSON actor field |
| Crash after COMMIT before reply | Duplicate retry or uncertain outcome | Client reconciliation required; exactly-once not established |
| Stale fence after SIGKILL | Temporary write unavailability | Lease expiration; no automatic forced takeover |
| Socket replacement | Impersonated server | Verified client helper checks peer PID/UID; raw clients must use it |
| Disk exhaustion / power loss | Journal availability or durability failure | Not qualified; separate power-loss and media testing required |
| Misprovisioned ownership | Client DB access | Strict directory/file checks; privileged deployment audit required |
| Unprotected database | Bypass of admission triggers | ProductionWriteService refuses non-v2 journals |

**Safety decision: NO-GO** for physical life-support control.
