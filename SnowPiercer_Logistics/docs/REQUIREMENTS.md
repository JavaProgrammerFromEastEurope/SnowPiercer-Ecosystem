# LOG-CORE-001 requirements
- R-001: Typed immutable Cargo, Container, Location, Transfer, Mission models.
- R-002: Explicit cargo and mission finite state machines; invalid transitions fail closed.
- R-003: Atomic SQLite transaction for state, command receipt and append-only event.
- R-004: Durable replay returns identical result for identical command key, payload and principal; collisions rejected.
- R-005: Role-based authorization (admin/operator/auditor) at public ledger methods.
- R-006: Read-only verification checks SQLite integrity, foreign keys, valid states and internal event hash chain.
- R-007: Regression tests including post-commit process termination and reopen.
- R-008: Production readiness remains NO-GO until independent end-to-end safety evidence.
