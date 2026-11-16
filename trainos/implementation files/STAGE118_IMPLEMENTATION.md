# Stage 118 — expired lease and competing recovery owners

## Scope

Added a cross-process regression test for the recovery journal's expired-lease
rules. A real child process owns an attempt while its lease is made expired in
SQLite. Both lease renewal and success completion must be rejected; a second
process must not steal a still-live owner's attempt. Once the owner exits, the
journal must first record interruption as `FAILED`, require explicit retry
authorization, and permit exactly one of two simultaneous retry claimants to
acquire the next fencing token.

No production code was changed: this stage validates existing ownership and
fencing contracts under a combined expiry/restart/contention scenario.

## Acceptance criteria

- Expired leases cannot be renewed or used to finish while the old owner remains alive.
- Another process cannot take over a live owner's `IN_PROGRESS` row.
- After owner exit, interruption is durable and explicit retry authorization is required.
- Two concurrent authorized claimants yield exactly one new owner.
- The successful retry increments attempt count and fencing token exactly once and ends in `SUCCEEDED` with ownership cleared.

## Validation results

- Focused Stage 104 and Stage 113–118 tests: **18 passed**.
- Full test suite: **730 passed**.
- `python -m compileall -q kernel tests`: passed.
- AST audit of Python files under `kernel/` and `tests/`: passed, 0 parse errors.

## Limitations

The test uses local SQLite and same-host PID liveness. It does not prove distributed
lease safety across hosts, PID namespaces, or production transport hardware.
