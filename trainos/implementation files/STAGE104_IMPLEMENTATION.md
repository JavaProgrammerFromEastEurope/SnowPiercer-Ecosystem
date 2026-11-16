# TrainOS Stage 104 — Fenced recovery ownership leases

## Change

- Added the nullable `lease_expires_at` journal column with an additive SQLite migration for older databases.
- Every newly created or explicitly authorized retry attempt receives a bounded ownership lease (default 300 seconds; maximum 86,400 seconds).
- Added `renew_lease()`, which atomically verifies the current run UUID, fencing token, `IN_PROGRESS` state, and unexpired lease before extending it. Renewal does not change the fencing token.
- An expired lease cannot be resurrected. A still-live or unknown local owner cannot finish after lease expiration; reconciliation may finalize only after the prior PID is confirmed absent and the recovery path independently verifies the candidate.
- Lease renewal and completion are serialized through SQLite `BEGIN IMMEDIATE`; independent store connections observe the same durable state.
- Startup recovery currently performs synchronous backup/verification without a heartbeat callback, so its initial lease is bounded at 24 hours. A future heartbeat-aware execution path is required for workloads that can exceed this window.

## Tests

`tests/stage104/test_recovery_owner_leases.py` covers successful renewal, stale-owner rejection, expired lease rejection, duration validation, and visibility/serialization across independent connections.

## Validation

- Focused regression suite: 25 passed.
- Full test suite: 692 passed.
- `python -m compileall -q kernel tests`: passed.
- AST parse audit: 2,583 Python files, zero parse errors.
- ZIP integrity: verified with `unzip -t` after archive creation.

## Limits

This is a local SQLite/PID-based lease, not a distributed consensus or hardware fencing mechanism. Wall-clock adjustments, PID reuse/namespaces, remote processes, and external side effects remain deployment concerns. Real train-control safety requires independent fail-safe protections and certification.
