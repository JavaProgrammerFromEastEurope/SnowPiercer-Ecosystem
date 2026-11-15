# RailSystem roadmap

| Stage | Domain | Deliverable | Acceptance evidence |
|---|---|---|---|
| RAIL-ARCH-001 | Architecture | subsystem inventory, boundaries | reviewed architecture |
| RAIL-REQ-001 | Requirements | traceable requirements | requirements matrix |
| RAIL-SAFE-001 | Safety | preliminary hazard analysis | hazard log |
| RAIL-IF-001 | Integration | TrainOS interface specification | contract tests |
| RAIL-SIM-001 | Digital twin | isolated simulator | deterministic scenarios |
| RAIL-OPS-001 | Operations | timetable and route planning | simulation tests |
| RAIL-VER-001 | Verification | CI and regression suite | reproducible reports |

Stages are domain-named rather than numbered by release. RAIL-ARCH-001: architecture registry and validator implemented; automated local verification passed; architecture review pending. Other stages not implemented.

RAIL-REQ-001: initial requirements registry and validation implemented; formal review pending.

RAIL-SAFE-001: preliminary hazard log and structural validator implemented; independent hazard analysis and safety review pending.

RAIL-IF-001: versioned non-actuating TrainOS observation contract, local adapter and contract tests implemented; live integration and security review pending.

RAIL-SIM-001: deterministic, isolated in-memory 1D simulation prototype implemented; software tests passed; physical model validation and safety review pending.

RAIL-OPS-001: virtual directed network, deterministic nominal route planning, conflict-aware timetable reservations, and DigitalTwin adapter implemented; local tests passed; operations and safety review pending.

RAIL-VER-001: stdlib unittest regression runner, explicit stage-to-test mapping, SHA-256 source manifest, deterministic evidence schema and optional external JSON report. Local evidence is not certification; review and CI integration pending.

RAIL-CI-001: local CI workflow scaffold, strict release gates and tests implemented; independent baseline approval and hosted CI execution pending.

RAIL-EVID-001: candidate baselines and offline provenance checks; independent signature verification intentionally absent, so release approval remains BLOCKED. Safety/operations NO-GO.

- RAIL-TRUST-001: offline Ed25519 trust verification and strict release gate; external atomic state integration outstanding.

- RAIL-TRUST-002: transactional SQLite replay admission, production CLI fail-closed, negative and POSIX process tests; trusted provisioning, durable external anchoring and real-world qualification outstanding.

- RAIL-TRUST-003: local filesystem anchored admission and offline recovery prototype; operational NO-GO.

- RAIL-TRUST-004 — Independent Trust Anchor & Production Recovery Fencing: PARTIAL; fail-closed external provider contract and signed offline permits; production BLOCKED.
- Proposed RAIL-TRUST-005 — Atomic External Anchor Transactions & Unified Production Admission: not implemented.

- RAIL-TRUST-005: unified production CLI admission and staged external-CAS reconciliation prototype; independent provider and E2E proof pending, NO-GO.
RAIL-TRUST-006: experimental same-UID IPC admission boundary; 222 tests; production NO-GO.
Next: RAIL-TRUST-007 — Atomic Startup Publication & Recovery Fencing Verification.

- RAIL-TRUST-007 (v0.17): startup inspection and socket publication under one lock; partial verification; NO-GO.
