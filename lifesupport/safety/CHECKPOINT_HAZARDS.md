# LIFE-CORE-005 — Preliminary Safety Analysis

| Hazard | Potential cause | Mitigation | Residual risk |
|---|---|---|---|
| Undetected journal truncation | Lost tail events | Externally protected signed anchor | Unanchored tail may be lost |
| Forged checkpoint | Unauthorized file modification | HMAC authentication | Compromised key defeats authentication |
| Anchor rollback | Replacement by older signed anchor | Local monotonic check when replacing | External immutable counter not implemented |
| Corrupt backup | Disk error or modification | SHA-256 manifest, HMAC, replay, SQLite integrity check | Concurrent adversarial replacement not fully handled |
| Loss of live database | Disk failure | Restore to a new path after verification | RPO/RTO not measured |
| Unsafe physical activation | Mistaking logical state for equipment safety | No physical command interfaces; NO-GO | Requires independent system safety validation |
| Partial backup publication | Crash between backup and manifest writes | Verification required before restore | Cleanup and atomic bundle publishing future work |

Safety claims are limited to tests performed on offline logical data.
