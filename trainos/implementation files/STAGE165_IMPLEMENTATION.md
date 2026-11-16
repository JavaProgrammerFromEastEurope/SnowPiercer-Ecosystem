# Stage 165 — Fail-closed inspection of damaged journals

## Changes

- `ExecutionJournalConsistencyChecker.inspect()` converts storage/record corruption encountered while reading the idempotency record, binding count, or execution history into a `CONFLICT` report.
- The report is diagnostic only and never repairs either SQLite journal.
- Corrupt/unreadable journals cannot authorize dispatch; the reason identifies which journal read failed and includes the exception class without leaking database contents.
- Regression tests corrupt a persisted idempotency fingerprint and remove the audit table between close/reopen cycles, verifying fail-closed behavior and preservation of the claim record.

## Validation scope

These are software regression tests for selected corruption cases, not a guarantee against every SQLite/media failure mode and not certification for physical train control.
