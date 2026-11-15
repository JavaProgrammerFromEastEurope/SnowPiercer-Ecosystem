# LIFE-CORE-007 preliminary hazard analysis

| Hazard | Cause | Mitigation | Residual limitation |
|---|---|---|---|
| H-ADM-01 stale writer | old process bypasses coordination | SQLite insert trigger | privileged clients can remove trigger |
| H-ADM-02 history rewrite | update/delete event | immutable event triggers | file replacement remains possible |
| H-ADM-03 incomplete migration | interruption during DDL | transaction and rollback | filesystem faults not tested |
| H-ADM-04 incorrect admission | compromised application/UDF | lease checked twice inside transaction | malicious client can spoof UDF |
| H-ADM-05 unauthorized recovery | local DB access | require token for migration | no OS ACL/HSM validation |
| H-ADM-06 corrupt journal | altered events | replay before migration | external anchor not independently enforced |

No physical actuation is authorized. System-level hazard assessment, threat modeling and hardware-in-loop verification remain outstanding. Operational decision: NO-GO.
