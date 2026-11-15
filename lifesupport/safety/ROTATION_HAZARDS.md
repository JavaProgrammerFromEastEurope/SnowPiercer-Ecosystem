# LIFE-CORE-010 Preliminary Hazard Register

| Hazard | Failure mode | Current mitigation | Residual risk |
|---|---|---|---|
| LIFE-HZ-010-01 | Key loss | Explicit dual-key intent | Recovery impossible without escrow |
| LIFE-HZ-010-02 | Interrupted rotation | Pending intent and read-only classification | No automatic cross-file atomicity |
| LIFE-HZ-010-03 | Forged intent | HMAC from both keys | Compromised keys defeat protection |
| LIFE-HZ-010-04 | Stale writer | Fencing check | Older APIs may bypass pending gate |
| LIFE-HZ-010-05 | Tampered anchor | MAC verification | Privileged attacker may replace artifacts |
| LIFE-HZ-010-06 | Power loss | fsync pending and anchor | Directory durability not guaranteed for pending file |
| LIFE-HZ-010-07 | Operational mis-reconciliation | Fail-closed, read-only inspection | Human error; manual procedures not validated |

**Decision: NO-GO for physical or safety-critical operation.**
