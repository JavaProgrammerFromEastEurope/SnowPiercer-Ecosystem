# RAIL-TRUST-005 — Atomic External Anchor Transactions & Unified Production Admission

## Requirements / contracts
- RT005-01: production release CLI must use the unified strict admission path; unsigned legacy CLI admission is forbidden.
- RT005-02: the same exclusive owner-controlled flock protects admission and offline recovery.
- RT005-03: durable SQLite PREPARED must precede external monotonic CAS; CAS precedes local anchor replacement and SQLite IDLE commit.
- RT005-04: any ambiguous or interrupted transaction remains fenced until explicit signed recovery.
- RT005-05: permits are scoped to sequence/action and consumed in the SQLite recovery transaction.
- RT005-06: no independent provider means no production PASS.

## Protocol
Under admission.lock: verify all three stores at IDLE, verify signed release attestation and source manifest, SQLite PREPARED commit, external provider compare-and-swap, fsync+rename local anchor, SQLite IDLE commit. Recovery under the same lock compares external state with the old/pending value, reconciles or aborts, and consumes signed permit in SQLite. Ambiguous states refuse progress.

## Safety / limitations
This is a software release gate, never a movement authority. IndependentAnchor is a contract, not a supplied independent service. The provider must authenticate callers, provide durable monotonic CAS, resist rollback, and survive host compromise. SQLite, local anchor and external CAS do not share a true atomic commit; the durable PREPARED phase is a recovery fence. SQLite and permit ledger can be rolled back together by a privileged attacker; permits are not independently consumed. No UID broker, IPC server, socket identity verification, all-boundary SIGKILL matrix, or real hardware-backed end-to-end verification is supplied. Legacy library functions remain callable and cannot be claimed universally fenced. No physical or production admission is authorized.
