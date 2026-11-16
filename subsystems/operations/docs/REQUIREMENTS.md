# SP-OPS foundation requirements and acceptance matrix

| ID | Requirement | Foundation evidence | State |
|---|---|---|---|
| OPS-REQ-001 | Enumerate all nine official module IDs exactly once | `config/catalog.json`; catalog tests | Implemented locally |
| OPS-REQ-002 | Preserve archived baselines and distinguish them from newer external releases | snapshot metadata; README | Implemented locally |
| OPS-REQ-003 | Detect absent/mismatched artifact and unsafe paths | `ops_core.py`, adversarial tests | Implemented locally; no hostile filesystem TOCTOU guarantee |
| OPS-REQ-004 | Flag cyclic readiness dependencies | `dependency_cycles`, tests | Implemented locally |
| OPS-REQ-005 | Retain an explicit, conservative NO-GO independent of software PASS | `assess`, tests | Implemented locally; advisory only |
| OPS-REQ-006 | Define typed interfaces and authority separation | `contracts/interfaces.json` | Proposed; not integrated |
| OPS-REQ-007 | Demonstrate end-to-end multi-UID control path with MAC/LSM and a separate security witness | none | BLOCKED |
| OPS-REQ-008 | Demonstrate physically representative HIL digital twin, fail-safe transitions and power loss | none | BLOCKED |
| OPS-REQ-009 | Approve cross-system hazards, independent assurance, acceptance and emergency drills | none | BLOCKED |
| OPS-REQ-010 | Prove software supply-chain roots and rollback-resistant deployed binaries | none | BLOCKED |
| OPS-REQ-011 | Establish signed change authority, independent operators and rollback procedure | plan only | BLOCKED |
| OPS-REQ-012 | Approve measured progress weights and complete work breakdown before publishing any percent | none | BLOCKED (percentage null) |

Source checks can pass while operational admission remains NO-GO. Statuses reflect the supplied snapshot, not externally published current releases.
