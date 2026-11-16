# Legacy Transaction Adapter v1

## Status
Additive, opt-in compatibility adapter. It does not replace `TransactionEngine`, `Ledger`, `TransactionRegistry`, or `BalanceCalculator`; no existing call sites are migrated.

## Mapping rules
- Only `TransactionType.TRANSFER` is supported.
- Both account IDs must be explicit and distinct.
- Legacy `currency_id` must have an explicit mapping to an uppercase three-letter currency code.
- Each currency code must have an explicit minor-unit exponent. No currency metadata is guessed.
- Amounts must be finite, positive, and exactly representable at the configured exponent. The adapter rejects excess precision; it never rounds.
- `from_account` maps to a debit and `to_account` to a credit. This matches the legacy `BalanceCalculator` convention where source balance decreases and destination balance increases.
- `transaction_id` becomes the ledger `operation_id`; identical retries are idempotent, changed content under the same ID is rejected by the ledger.
- Deposit, withdrawal, tax, salary, reward, fine, and grant are intentionally unsupported until their external/clearing account semantics are explicitly specified.

## Compatibility boundary
The adapter is only invoked when a caller explicitly constructs it and calls `to_journal()` or `append()`. The legacy API and behavior remain unchanged. It does not authorize real-money use.

## Required before production
Add a currency registry rather than ad-hoc maps; establish account ownership and authorization; specify deposit/withdrawal/fees/refunds semantics; add access controls, audit export, backup/restore drills, independent reconciliation, threat modelling, operational monitoring, and compliance review. The current ledger's signed balance convention is not by itself a complete accounting chart-of-accounts policy.
