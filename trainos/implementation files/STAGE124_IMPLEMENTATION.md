# Stage 124 — Concurrent Retry Limit Exhaustion

## Scope

Adds a multiprocess regression test for simultaneous `authorize_retry()` and
`begin_attempt()` requests after the durable `max_attempts` limit has been
reached. No production code changes were needed.

## Test behavior

- Creates one attempt with `max_attempts=1` and finishes it as `FAILED`.
- Starts four independent spawned processes at a barrier: two request retry
authorization and two attempt to begin again while supplying a larger limit.
- Requires every request to be blocked with `maximum recovery attempts reached`.
- Reopens the SQLite database and checks that status, attempt count, configured
limit, owner fields, fencing token, lease, and authorization fields are unchanged.

## Validation

Validation completed:

- Focused Stage 120–124 regression tests: **10 passed** in 7.49 s.
- Full test suite: **741 passed** in 23.55 s.
- `python -m compileall -q kernel tests`: passed.
- AST audit: **2,602 Python files**, 0 parse errors.

## Limitations

This tests process-level contention against a local SQLite database. It does
not establish behavior under power loss, filesystem corruption, or distributed
multi-host failure, and is not transport safety certification.
