# Preliminary hazard analysis — LIFE-CORE-008

| Hazard | Consequence | Mitigation | Residual risk |
|---|---|---|---|
| Guard removed | Unauthorized append | Verify canonical trigger SQL before write | DB admin can forge schema and seal |
| Guard modified | Invalid protection policy | Fail closed on mismatch | In-process SQLite extension / privileged access |
| Seal missing or changed | Unknown protection state | Fail closed on open and write | Seal is stored in same trust domain |
| Partial migration | Inconsistent admission mode | Transactional migration and rollback | Storage hardware failures not tested |
| Legacy API bypass | Unfenced append | v2 check in admitted writer and SQLite triggers | Other privileged APIs may bypass |
| False integrity alarm | Loss of availability | Explicit quarantine and investigation | Operational procedures not implemented |

NO-GO for safety-critical or physical control use. Independent review and fault-injection testing are required.
