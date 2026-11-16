# Security requirements register — v0.1.0

| ID | Criticality | Requirement | Current evidence | Status |
|---|---|---|---|---|
| SEC-REQ-001 | High | Every request has a single canonical UUID, principal, resource, action, policy version and correlation ID; unknown fields refused. | unit tests 23–31 | TESTED (simulation) |
| SEC-REQ-002 | Critical | Missing policy match and privileged actions cannot generate an executable permit. | unit tests 1–6, 18 | TESTED (simulation) |
| SEC-REQ-003 | High | Duplicate request ID is rejected atomically in SQLite. | unit tests 7–8, 20–21 | TESTED (local SQLite) |
| SEC-REQ-004 | High | Audit references are bound to a versioned decision; failures of audit integrity and writes block admission. | unit tests 9–15, 22 | TESTED (local SQLite) |
| SEC-REQ-005 | Critical | Production admission requires externally verified OS-enforced MAC/LSM and cross-UID broker identity. | permanent NO-GO fence; no real OS proof | BLOCKED |
| SEC-REQ-006 | Critical | Recovery requires an independent monotonic anti-rollback root, durable permit authority and independent witness. | no external root in environment | BLOCKED |
| SEC-REQ-007 | Critical | An independent service manager supervises startup, recovery, kills and restarts, including all legacy entrypoints. | no authority installed | BLOCKED |
| SEC-REQ-008 | Critical | Real separate UIDs and mandatory crash fault-injection matrix cover SQLite, CAS, phase journal, witness, permit and IPC boundaries. | not run; no safe real environment configured | BLOCKED |
| SEC-REQ-009 | Critical | Safety case, hardware-interlock independence, operator override and independent review support physical deployment. | scope only | BLOCKED |
| SEC-REQ-010 | High | Existing TrainOS and other modules retain their APIs and evidence. | additive workspace changes, original six probes still run | PARTIALLY TESTED |

`TESTED` is limited to the named software reference, never a physical or production claim.
