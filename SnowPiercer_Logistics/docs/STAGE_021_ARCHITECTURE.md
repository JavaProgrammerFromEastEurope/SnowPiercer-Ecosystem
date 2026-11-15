# LOG-CORE-021 architecture

`TimedLogisticsLedger` extends the existing SQLite cargo model. The original
`LogisticsLedger._command` now calls a default no-op `_admit_command` policy hook
inside its existing write transaction. The opt-in subclass uses this hook to
check revision, expiry and replay receipts; existing ledger users keep their
previous behavior.

1. Snapshot and validate the closed, flat JSON envelope. Resolve host-supplied
   `Principal` permissions separately from the envelope.
2. Check a trusted host clock, then enter the original per-ledger RLock.
3. Dispatch the existing typed cargo operation. `BEGIN IMMEDIATE` serializes
   writers even across independent SQLite connections.
4. Recheck time after obtaining the database write lock. For a new request,
   compare `COUNT(events)` with `expected_events`, then insert a receipt into
   `integration_commands`. This receipt, original idempotency entry, cargo
   mutation and hash-chain event commit or roll back together.
5. For a repeated command, require the same canonical envelope and principal.
   Reuse the original cached result without a second cargo effect. A now-stale
   revision is acceptable only for an exact, unexpired replay of an already
   committed operation.

The new table stores a SHA-256 content fingerprint, not an authentication
signature. It does not independently protect a SQLite file against its owner,
root, tampering or rollback. No witness CAS, permit consumption, external LLM,
robot, drone or railway command is invoked.
