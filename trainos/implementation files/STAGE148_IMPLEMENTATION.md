# Stage 148 — Whole-journal validation before mutations

## Change

Added `_assert_all_persisted_rows_valid()` to scan and validate every durable recovery row before state-changing operations (`begin_attempt`, lease renewal, finish, and retry authorization). A healthy target record no longer permits mutation when a different row in the same journal has contradictory or malformed metadata.

## Safety behavior

- Validation runs inside the `BEGIN IMMEDIATE` transaction, before target-row mutation.
- Any malformed row raises `RecoveryAttemptBlocked`; the transaction is rolled back.
- The implementation does not silently repair or delete forensic evidence.
- This is a fail-closed integrity check, not a tamper-proof audit mechanism. The full scan is appropriate only while the recovery journal remains bounded.
