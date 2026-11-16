# TrainOS Stage 134 — Recovery journal timestamp integrity

## Scope

Audited `EventLogRecoveryAttemptStore` timestamp reads and lease comparisons. Durable journal timestamps are generated with explicit timezone offsets, but Python accepts timezone-naive ISO timestamps; comparing those against timezone-aware UTC timestamps can raise an unclassified `TypeError`.

## Changes

- Validate `started_at`, `updated_at`, and `lease_expires_at` whenever a journal row is decoded.
- Reject missing `updated_at`, malformed timestamps, and timezone-naive timestamps with `RecoveryAttemptBlocked` and a manual-reconciliation message.
- Preserve corrupt values as evidence; validation does not auto-repair the journal.
- Add regression coverage for malformed and naive timestamps, plus an expired but syntactically valid lease that must not be renewed.

## Safety boundary

An expired lease is not itself malformed. Existing ownership/process rules still decide whether an interrupted attempt can be reconciled. These tests cover local SQLite journal integrity, not distributed locking or real-train safety certification.
