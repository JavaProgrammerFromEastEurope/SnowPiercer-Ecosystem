# Stage 119 — stale worker after fencing-token takeover

## Scope

Added a multiprocess regression test proving that a worker holding an older
`owner_run_id` and fencing token cannot renew a lease, finish successfully, or
mark failure after a new attempt has acquired a higher fencing token.

The test deliberately modifies the recorded PID to simulate a failover supervisor
that has classified the recorded owner as dead while a stale actor still exists.
This is an adversarial test fixture, not a proposed production recovery procedure.
The test checks that all stale mutations are rejected and that the new owner's
status, identity, token, PID, and lease remain unchanged until its valid completion.

No production code changed in this stage.

## Acceptance criteria

- An interrupted attempt is persisted as `FAILED` and requires explicit retry authorization.
- A new attempt increments `fencing_token` exactly once and receives a distinct run ID.
- The old run ID/token cannot renew, finish success, or finish failure.
- Rejected stale calls do not alter the new owner's durable state.
- The current owner can finish once, clearing owner and lease while preserving the new token.

## Validation

- Focused Stage 104 and Stage 113–119 tests: **19 passed**.
- Full test suite: **731 passed**.
- `python -m compileall -q kernel tests`: passed.
- AST audit of Python files under `kernel/` and `tests/`: passed, 0 parse errors.

## Limitations

This test isolates stale-token rejection in a local SQLite journal. It does not establish
safety across distributed hosts, prove a real supervisor's failure detector, or certify
TrainOS for operation of transport hardware.
