# LIFE-CORE-019 preliminary safety analysis

| Hazard | Mitigation | Residual risk |
|---|---|---|
| Torn SQLite/anchor update | signed pre-commit intent, reconciliation | power loss may reorder persistence |
| Lost response after COMMIT | receipt replay | client may not retry |
| Corrupted intent | fail closed | manual intervention required |
| Malicious anchor replacement | HMAC authentication | compromised key defeats control |
| Joint rollback DB/anchor/intent | no reliable protection | independent monotonic trust root required |
| Concurrent independent writers | exclusive service assumption | legacy same-UID API bypass |
| Unauthorized client | SO_PEERCRED allowlist | root/service UID privileged |
| Stalled recovery | refuse service | availability loss |
| Physical command repeated | no hardware side-effect dedup | physical control forbidden |

**Safety decision: NO-GO** for real life-support actuation. No IEC/EN certification or power-cut evidence.
