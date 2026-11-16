# TrainOS Stage 99 — Cross-process recovery ownership

## Scope

Audited the durable recovery-attempt journal and prior thread-level concurrency tests. The journal already serialized SQLite state transitions, but when a second process encountered an `IN_PROGRESS` attempt owned by a different PID, it unconditionally classified that attempt as interrupted. This could mark a still-running recovery as failed and create conflicting ownership decisions.

## Implementation

- Added a conservative local-process liveness check using `os.kill(pid, 0)`.
- A competing process now fails closed when the recorded owner appears alive; the journal remains `IN_PROGRESS`, and the attempt counter is unchanged.
- An absent/dead owner still transitions to `FAILED` and requires explicit retry authorization.
- Documented the limitation: PID liveness is not a distributed lease and does not solve PID reuse or differing container/remote PID namespaces.
- Added `tests/stage99/test_recovery_cross_process_ownership.py` covering two genuinely independent processes and explicit retry after an abandoned owner.

## Validation

- Focused tests: `PYTHONPATH=. pytest -q tests/stage99 tests/stage93 tests/stage98` — **7 passed**.
- Full suite: `PYTHONPATH=. pytest -q` — **679 passed**.
- `python -m compileall -q kernel tests` — passed.
- AST audit — **2,578 Python files, 0 parse errors**.

## Safety boundary

This stage improves same-host process ownership handling. It is not a distributed lock, a tamper-proof journal, or evidence of production readiness. Multi-host deployments need a robust lease/owner identity and fencing tokens; real transport safety still requires independent safety controls and hardware validation.
