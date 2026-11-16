# TrainOS Stage 77 — Persistent event-log integrity

## Changes
- Added SHA-256 hash chaining to `CommandEventStore`, binding each stored event envelope to the preceding event hash.
- Added a read-only `verify_integrity()` audit for event hash mismatches, broken links, and sequence gaps.
- Added a schema migration for databases created before hash columns existed. Existing rows are re-anchored during migration; this cannot establish authenticity of legacy rows before migration.
- Added regression tests for clean restart, payload tampering, middle-row deletion, and idempotent duplicate append.

## Verification
- Focused tests (stages 74–77): 16 passed.
- Full suite: 589 passed in 3.89s; pytest exited successfully.
- `compileall` passed.
- AST parse of all kernel Python files passed.
- ZIP integrity verified.

## Limitations
- A local hash chain is not tamper-proof against an attacker able to rewrite the entire database and recompute hashes.
- Deletion of the final suffix cannot be reliably detected without an external trusted checkpoint/anchor. Production deployment should periodically export signed chain heads to independent storage.
- Legacy rows are anchored at migration time, not cryptographically authenticated retroactively.
- This event store is not a safety-certified train-control log.
