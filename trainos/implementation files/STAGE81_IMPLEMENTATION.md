# Stage 81 — Event Log Recovery Gate

## Scope
- Added `EventLogRecoveryGate` and structured `EventLogRecoveryAssessment`.
- Distinguishes `verified`, `damaged`, and `insufficient_data` states.
- `require_verified()` fails closed unless the log passes its internal hash-chain checks and matches the latest trusted anchor.
- Exports recovery gate, status, anchor store, and signed-anchor functions from `kernel.command.events`.
- Added tests for clean restart/recovery, missing anchors, tampering, rollback, and invalid API arguments.

## Limitations
The gate is opt-in: callers must invoke it before consuming recovered history. A local SQLite anchor database is not immutable or independently trusted if an attacker can rewrite it. HMAC keys and remote/WORM storage are not managed here. This is not a railway safety function and must not directly authorize train motion, braking, or levitation.
