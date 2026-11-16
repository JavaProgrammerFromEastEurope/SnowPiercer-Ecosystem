# Financial Ledger Contract v8 — Integrity and concurrent-backup audit

Date: 2026-10-24

## Scope

This stage strengthens the independent consistency audit of the experimental SQLite ledger. It does not connect the ledger to live payments or change existing TrainOS financial APIs.

## Changes

- `FinancialLedger.verify_integrity()` now checks SQLite integrity, foreign-key consistency, journal value-object invariants, operation fingerprints, reversal inverse relationships, and the independent reconciliation result.
- The integrity report exposes `foreign_key_errors` and `reconciliation_ok` separately, so callers can distinguish storage-relationship failures from accounting inconsistencies.
- Added tests for out-of-band posting tampering, foreign-key violations, altered reversal postings, and a consistent SQLite backup taken while independent writer connections are appending journals.
- The concurrent-backup test initializes the schema before competing writers start and verifies the backup itself with both integrity and reconciliation checks.

## Verification

- Financial ledger + legacy adapter tests: 48 passed.
- Targeted TrainOS tests for stages 172–177: 15 passed.
- Financial ledger + legacy adapter tests: 48 passed.
- `compileall`: to be recorded in the build manifest after execution.
- Static Python AST scan: to be recorded in the build manifest after execution.

## Limits

The tests simulate database corruption through direct SQL and are not a security certification. Hashes stored inside the same database detect accidental or unsophisticated changes, but cannot authenticate data against an attacker who can rewrite both records and hashes. For that, use a separately protected signing key or external immutable checkpoint. A consistent SQLite backup is not an off-host disaster-recovery policy. Full TrainOS suite, load testing, and production threat modelling remain outstanding.

## Status

`experimental / isolated prototype`. Not approved for real-money transactions. SnowPiercer integration remains gated on full-suite CI, external integrity anchoring, access-control design, reviewed currency/accounting rules, and an independent security review.
