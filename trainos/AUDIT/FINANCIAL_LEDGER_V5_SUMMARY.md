# Financial Ledger Contract v5 — Currency Registry and Retry Integrity

## Scope

This stage is additive. It introduces an explicit application-configured currency metadata allowlist and tightens reversal retry semantics. Existing legacy transaction APIs and default adapter construction remain supported.

## Changes

- `CurrencySpec` validates a three-letter uppercase code, a minor-unit exponent from 0 through 6, and an enabled flag.
- `CurrencyRegistry` rejects duplicate codes, returns only registered currencies, and rejects disabled currencies by default.
- `LegacyTransactionAdapter` accepts an optional registry and checks configured exponents against it. Existing callers without a registry remain compatible.
- Reversal retries now compare the requested compensating journal fingerprint. Reusing the same reversal ID with a changed description/content raises `IdempotencyConflict` instead of silently returning a no-op.
- Added tests for registry configuration, disabled/unregistered codes, exponent mismatch, and reversal retry content conflicts.

## Important limitations

The registry is an explicit allowlist configured by the application. It is not a complete, live, or officially sourced ISO 4217 dataset. The ledger itself still accepts any syntactically valid currency code in direct `JournalEntry` calls unless callers enforce registry validation at the service boundary. This is intentional for backward compatibility and must be addressed before any production integration.

No production payment provider, banking settlement, tax calculation, access-control system, or Japan-specific regulatory workflow is integrated. The ledger remains a prototype. No real-money use is approved.

## Verification

Results are recorded in `AUDIT/financial_ledger_v5_manifest.json`. The full TrainOS test suite is not claimed unless it is explicitly run to completion.
