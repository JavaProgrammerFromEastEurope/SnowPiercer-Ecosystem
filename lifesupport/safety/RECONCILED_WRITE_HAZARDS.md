# Preliminary safety analysis — NO-GO

| Hazard | Mitigation | Residual risk |
|---|---|---|
| Duplicate command after lost response | Atomic request receipt and replay | External physical side effects not covered |
| Process killed before COMMIT | SQLite rollback, tested with SIGKILL | Power-loss durability unproven |
| Process killed after COMMIT | Durable receipt and replay, tested | Replaced or rolled-back database may lose receipt |
| Request ID reused with changed arguments | SHA-256 canonical binding and conflict rejection | Hash collision assumptions; no independent anchor |
| Unauthorized client | Kernel SO_PEERCRED and DAC | Root/service UID can bypass |
| Crash while holding lease | Expiring lease; retry later | Up to 2-second unavailability; clock changes |
| Stale or forged socket | Inode/type/ownership validation and connected PID/UID check | Privileged local adversary can interfere |
| Supervisor itself killed | External process manager required | Not automatically recovered |
| Denial of service | Framing limit inherited from Stage 012 | No rate limit or queue fairness guarantee |
| Physical actuation | Not implemented | Not certified for life support |

Safety verdict: NO-GO for actual life-support hardware.
