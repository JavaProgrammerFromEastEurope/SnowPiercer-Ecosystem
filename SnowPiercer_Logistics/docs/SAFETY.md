# Safety assessment
| Hazard | Mitigation in this stage | Residual risk |
|---|---|---|
| Duplicate command | Transactional idempotency receipt | No physical actuation exactly-once guarantee |
| Invalid state transition | Explicit FSM and transaction rollback | External systems not bound to FSM |
| Untrusted caller | RBAC on supplied Principal | Caller can forge identity; no production authentication |
| Crash during write | SQLite atomic transaction; post-commit SIGKILL-like exit test | No exhaustive crash-point fault injection |
| Concurrent writers | SQLite BEGIN IMMEDIATE | No multi-host distributed fencing |
| Ledger modification | Internal hash chain verification | No external trust anchor; full rewrite undetectable |
| Cargo capacity overload | Container positive capacity only | No cargo mass or aggregate load checks |
| Unsafe routing | No physical routing executed | No safety case for robots, trains, drones |

**Decision: NO-GO** for production and physical movement. Further evidence required: OS identity binding, authenticated IPC, recovery witness, multi-process crash matrix, physical interlocks and independent end-to-end verification.
