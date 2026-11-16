# Stage 123 — Retry-limit enforcement after repeated crashes

## Scope

Added regression coverage for the durable `max_attempts` limit across process restart and crash recovery.

- A child process exits with `os._exit()` immediately after the SQLite commit that starts the second attempt.
- On restart, the dead owner's `IN_PROGRESS` record is reconciled to `FAILED`; the count remains 2, the fencing token remains at the second attempt's token, and the lease is cleared.
- Both retry authorization and a new start are rejected once `attempt_count == max_attempts`, even if a caller supplies a larger `max_attempts` value to `begin_attempt()`.
- A separate single-attempt test verifies the configured limit cannot be raised by a later API call.

## Production changes

No production code changes were necessary. The tests exercise the existing transactional limit checks in `authorize_retry()` and `begin_attempt()`.

## Validation

Run focused Stage 122–123 tests and the complete test suite, compile checks, AST parsing audit, and ZIP integrity verification. These checks cover process-crash behavior with a local SQLite database; they do not establish power-loss durability, distributed failover safety, or certification for real train control.

## Verified results

- Focused tests for stages 113–123: **23 passed**.
- Full test suite: **740 passed**.
- `python -m compileall -q kernel tests`: passed.
- AST audit: all Python files parsed without errors.
