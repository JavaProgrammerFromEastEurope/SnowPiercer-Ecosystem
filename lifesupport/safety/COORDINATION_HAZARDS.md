# LIFE-CORE-006 preliminary hazard register

| Hazard | Cause | Mitigation in prototype | Residual risk |
|---|---|---|---|
| H-006-01 Split-brain journal writers | Competing instances | SQLite transaction + epoch lease | Legacy API bypass; uncooperative clients |
| H-006-02 Stale commands | Expired owner | Token/expiry check on write | No downstream physical actuator fencing |
| H-006-03 Clock discontinuity | Wall clock correction | Expiry checked twice | Backward clock jumps extend lease |
| H-006-04 Corrupted history | Disk or malicious modification | Full replay before acquiring/writing | No external trust anchor enforcement in coordination |
| H-006-05 Storage failure | Disk crash, network filesystem | SQLite transaction rollback | No fault injection, durability qualification or distributed consensus |
| H-006-06 Unsafe recovery | Uncoordinated backup/restore | Require token for fenced recover | LIFE-CORE-005 backup APIs remain unfenced |
| H-006-07 Forged lease | Writable coordination table | Registry fingerprint check | No authentication/authorization for DB writers |

**Decision:** NO-GO for physical life-support control. Require formal hazard analysis, independent interlocks, trusted time/consensus design, controlled storage API, hardware-in-the-loop testing and field verification.
