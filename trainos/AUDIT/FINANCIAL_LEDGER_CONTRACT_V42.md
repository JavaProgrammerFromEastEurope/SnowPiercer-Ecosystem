# Financial Ledger Contract — v42 (Stages 328–337)

## Scope

This release adds ten regression contracts around execution identity, legal state transitions, JSON payload validation, and persistence across database reopen. The tests exercise the local SQLite command idempotency ledger only.

## Stage register

| Stage | Contract | Expected safety property |
|---:|---|---|
| 328 | Completion of a command bound to an execution ID requires that ID | Missing binding cannot complete the record |
| 329 | Completion rejects a mismatched execution ID | Another execution cannot complete this record |
| 330 | A completed record cannot transition to UNKNOWN | Terminal completion is preserved |
| 331 | A completed record cannot be reconciled as not executed | Reconciliation cannot reverse a confirmed result |
| 332 | A CLAIMED record cannot be reconciled as not executed | Explicit uncertainty is required before reconciliation |
| 333 | One execution ID cannot be attached to two idempotency keys | Duplicate execution binding is rejected atomically |
| 334 | A repeated claim cannot change its execution binding | Original binding remains authoritative |
| 335 | Non-JSON-serializable payloads are rejected before insertion | Invalid payloads do not mutate the ledger |
| 336 | NaN payload values are rejected before insertion | Non-standard JSON numbers do not enter the ledger |
| 337 | Completed records survive closing and reopening the database | Durable state and result are preserved |

## Verification status

- New Stage 328–337 tests: run and passed (see `AUDIT/v42_new_pytest.txt`).
- Regression tests for stages 170–337: run result recorded in `AUDIT/v42_regression_pytest.txt`.
- Python AST syntax audit: result recorded in `AUDIT/v42_ast_audit.txt`.
- ZIP integrity and cache exclusion: result recorded in the v42 manifest.
- Full project suite and GitHub Actions: not run as part of this release unless explicitly recorded otherwise.
- External payment-provider integration: **NO-GO / not verified**. No live or sandbox payment was executed by these tests.

## Limitations

Passing these tests is evidence for local SQLite ledger contracts, not proof of distributed exactly-once execution, provider-side idempotency, payment settlement correctness, production security, or safety certification. Before sandbox payment tests, the provider adapter and Transaction Service boundary must be implemented and tested independently.
