# TrainOS Stage 127 — Ambiguous Retry-Authorization Commit

## Scope

Exercise the recovery-attempt journal's ambiguous-COMMIT path for `authorize_retry()`.
The simulated database connection commits the authorization durably and then raises an
`sqlite3.OperationalError`, representing a lost acknowledgement after commit.

## Assertions

- The store resolves the ambiguous outcome from a fresh SQLite connection and returns
  the exact committed `RETRY_AUTHORIZED` row.
- Operator, authorization reason, checkpoint fingerprint, attempt count, maximum, and
  fencing token remain consistent.
- Repeating authorization is rejected because the row is no longer `FAILED`.
- The explicit retry is consumed exactly once by `begin_attempt()`, incrementing attempt
  count and fencing token once and generating a new owner run ID.
- After the final allowed attempt fails, further retry authorization is blocked.
- A new store instance observes the durable terminal row after restart.

## Production changes

None. The existing exact-row ambiguous-COMMIT resolver is exercised by a regression test.

## Validation

Results are recorded in the Stage 127 completion response after focused tests, the full
pytest suite, compileall, AST parsing, and ZIP integrity checks have actually run.
