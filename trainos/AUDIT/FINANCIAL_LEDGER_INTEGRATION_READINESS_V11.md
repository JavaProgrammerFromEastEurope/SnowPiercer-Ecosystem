# Financial Ledger Integration Readiness — v11

Date: 2026-10-24

## Decision

**Decision: NO-GO for production payments; limited isolated experiments only.** The new ledger is an additive prototype. It must not replace the legacy transaction API or be connected to real customer balances or settlement providers until the gates below are closed.

## Transaction type coverage

The legacy enum contains eight types: `transfer`, `deposit`, `withdraw`, `tax`, `salary`, `reward`, `fine`, and `grant`. The adapter currently maps only `transfer`. All other types must fail closed until account semantics, authorization, fees/tax rounding, dispute/reversal policy, and idempotency scope are documented and tested. See `TRANSACTION_TYPE_MAPPING_V1.csv`.

## Test execution evidence

- Targeted financial ledger and Stage172–177 suites: **70 passed in 16.35s**.
- Full `pytest -q` attempt: **timed out at the environment's 180-second limit**, after reaching approximately 14% of collected tests. This is not a pass and no conclusion is made about the unexecuted tests.
- The full-suite timeout is a blocker for an integration-readiness claim. Investigate the slow/hanging test and split CI into deterministic shards before repeating.
- Static AST/compile checks from prior v10 packaging are not a substitute for the full test suite.

## Mandatory integration gates

1. Full test suite completes in CI; failures and timeouts are triaged, not ignored.
2. Every legacy transaction type has an explicit approved mapping or remains rejected by tests.
3. Currency codes and exponents come from a reviewed registry; currency registry updates are versioned.
4. Access control, account ownership, available-balance rules, settlement states, refunds, chargebacks, and authorization are specified.
5. Trusted checkpoint head is stored outside the database and independently protected against rollback.
6. Backup/restore drills include a trusted external checkpoint and reconciliation against an independent source.
7. Migration and adapter behavior are covered by compatibility tests with the legacy API unchanged.
8. Independent security and accounting review is completed before any real-money use.

## Non-goals / limitations

- No integration with payment providers, consumer accounts, or the SnowPiercer mobile app.
- No assertion that a double-entry prototype by itself provides a complete payment system.
- HMAC verification depends on key secrecy and separately protected trusted state; it does not protect against key compromise.

## Next work

First resolve the full-suite timeout and introduce a CI test matrix. Then implement explicit domain policies and mappings for one additional transaction type at a time, with tests and review. Do not add a broad generic mapping that guesses account roles.
