# TrainOS Stage 147 — persisted recovery-record validation

## Scope

Harden the SQLite recovery-attempt journal against invalid persisted key, reason,
timestamp, and attempt-limit values, including corruption introduced by an external
writer that bypasses normal API validation and SQLite CHECK constraints.

## Changes

- Validate persisted `attempt_key` and `reason` types and non-blank canonical values
  before exposing a recovery record or allowing a transition.
- Require both `started_at` and `updated_at`; validate timestamp syntax and explicit
  timezone offsets. Only `lease_expires_at` may be absent on inactive attempts.
- Continue validating `max_attempts` as a positive integer consistent with
  `attempt_count`.
- If a requested key is absent, run a narrow SQL audit for invalid persisted keys
  before returning `None` or inserting a new attempt. This prevents a damaged blank
  key from hiding a row while keeping the ordinary found-row path efficient.
- Add regression tests that corrupt rows directly through SQLite, verify reads and
  transitions fail closed, and verify the original values and attempt count remain
  unchanged. A normal lifecycle test guards against rejecting valid records.

## Verification

- Focused stages 130–147: 67 passed.
- Full test suite: 816 passed in 35.30 seconds (pytest exit code 0).
- `python -m compileall -q kernel tests`: passed.
- AST audit: 2,625 Python files parsed, 0 errors.
- ZIP integrity and excluded-path audit: performed for the distributed archive.

## Limitations

The SQLite journal is not tamper-proof and this stage is not a safety certification
for real train control. External modification that replaces one valid key with a
*different valid key* cannot be inferred from the row alone without an independent
trusted anchor or append-only audit source.
