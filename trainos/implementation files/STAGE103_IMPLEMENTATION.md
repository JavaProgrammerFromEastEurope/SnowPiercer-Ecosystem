# TrainOS Stage 103 — Live-owner-safe recovery reconciliation

## Change

Startup recovery previously attempted crash-window reconciliation whenever a candidate file existed and the journal said `IN_PROGRESS`. That could finalize an attempt while the recorded owner process was still alive. A PID is not a distributed lease, but a positive liveness result must prevent another invocation from taking over; an unknown PID must also fail closed.

- `RecoveryAttempt` now exposes the journaled `owner_pid` alongside the run ID and fencing token.
- Before reconciling an existing candidate for an `IN_PROGRESS` attempt, startup recovery checks the recorded PID.
- If the PID is alive or missing/unknown, startup returns `BLOCKED` with `recovery_owner_still_alive_or_unknown` and does not change the journal.
- Reconciliation can continue only when the recorded local PID is confirmed absent. Existing tests explicitly simulate the prior process having exited.
- Added Stage 103 tests verify live and unknown owner cases preserve the attempt status, owner run ID, and fencing token.

## Validation

Run `PYTHONPATH=. pytest -q tests/stage103 tests/stage102 tests/stage101 tests/stage100 tests/stage99 tests/stage98 tests/stage96 tests/stage95 tests/stage91` and the full suite, plus compileall and AST parse audit.

## Limits

PID liveness is only a conservative local guard. PID reuse, PID namespaces, remote workers, and external side effects require deployment-level leases/fencing enforcement. This change does not make TrainOS safe or certified for real train control.
