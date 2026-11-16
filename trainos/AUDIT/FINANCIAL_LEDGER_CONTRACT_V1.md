# Financial Ledger Contract v1 — implementation and verification

- Implementation: `kernel/economy/ledger_contract/`
- Tests: `tests/ledger_contract/`
- Legacy compatibility: no existing transaction modules or call sites modified.
- Status: isolated prototype; not approved for production payments.

## Verified in this build

Command run from canonical project root:

`PYTHONPATH=. python -m pytest -q tests/ledger_contract tests/stage21 tests/stage25 tests/stage3 tests/stage33 tests/stage125`

Result: **51 passed in 2.10s**.

The selected run covers the new contract tests plus existing transaction, currency,
consumption and crash-retry tests in the listed stage directories. It is not a full
TrainOS test-suite run.

## Contract behaviors covered by the new tests

- double-entry debit/credit balance and single-currency journals;
- positive integer minor-unit amounts;
- idempotent exact retries and conflict on changed content;
- durable reopen of a file-backed SQLite database;
- concurrent identical retries committing exactly once;
- per-account, per-currency signed balance queries.

## Not yet implemented / release blockers

FX and currency registry integration; authorization and account ownership; funds
availability/overdraft policy; fees; refunds/reversals; reconciliation; external
payment rails; audit export/tamper evidence; operational backup/restore testing;
formal migration plan; security and compliance review; load/HA qualification.
