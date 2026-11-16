# Financial Ledger Contract — v43 (Stages 338–347)

## Scope

This release adds ten contracts for durable dispatch reservation, cross-store dispatch protection, and reconciliation audit integrity. These tests exercise the local SQLite command idempotency ledger only.

## Stage register

| Stage | Contract | Expected safety property |
|---:|---|---|
| 338 | Dispatch reservation requires a bound execution identity | Unbound commands cannot cross the dispatch boundary |
| 339 | Dispatch reservation is single-use per generation | Repeated calls do not create another dispatch reservation |
| 340 | Dispatch reservation survives database reopen | Restart does not silently authorize a duplicate dispatch |
| 341 | UNKNOWN outcomes cannot be dispatched without reconciliation | Uncertainty remains blocked until explicit evidence resolves it |
| 342 | COMPLETED commands cannot be dispatched again | Terminal results cannot authorize another dispatch |
| 343 | Not-executed reconciliation resets the reservation but preserves generation | Every subsequent dispatch remains distinguishable in the audit history |
| 344 | Completed reconciliation requires the matching execution ID | Another execution cannot reconcile this record |
| 345 | Completed reconciliation audit preserves evidence and dispatch generation | The decision can be traced to the observed dispatch generation |
| 346 | Not-executed evidence cannot be reused after a later dispatch | Stale evidence cannot authorize another retry |
| 347 | Separate store instances cannot reserve the same dispatch twice | SQLite transaction boundaries protect the reservation across instances |

## Verification status

- New Stage 338–347 tests: 10 passed (see `AUDIT/v43_new_pytest.txt`).
- Regression tests for stages 170–347: 207 passed (see `AUDIT/v43_regression_pytest.txt`).
- Python AST syntax audit: result recorded in `AUDIT/v43_ast_audit.txt`.
- ZIP integrity and cache exclusion: recorded in the v43 manifest.
- Full project suite and GitHub Actions: not run as part of this release.
- External payment-provider integration: **NO-GO / not verified**. No sandbox or live payment was executed by these tests.

## Limitations

These contracts validate local SQLite behavior and selected multi-instance access. They do not prove provider-side idempotency, distributed exactly-once execution, payment settlement correctness, production security, or safety certification. Before sandbox payment tests, the provider adapter and Transaction Service boundary must be implemented and tested independently.
