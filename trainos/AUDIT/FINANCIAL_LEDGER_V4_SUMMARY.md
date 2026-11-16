# Financial Ledger Contract v4 — adapter summary

## Delivered
- Added `kernel/economy/ledger_contract/legacy_adapter.py`.
- Exported `LegacyTransactionAdapter` from the ledger-contract package.
- Added focused adapter tests in `tests/ledger_contract/test_legacy_adapter.py`.
- Added the mapping specification and a compatibility checklist.
- Left legacy transaction modules and their public API unchanged.

## Verification performed
- `PYTHONPATH=. pytest -q tests/ledger_contract tests/stage21/test_transaction_engine.py`: **31 passed**.
- `python -m compileall -q kernel/economy/ledger_contract tests/ledger_contract`: passed.
- AST parse across 2,663 Python files: **0 errors**.
- The test run emitted eight Python 3.13 multiprocessing `fork` deprecation warnings from existing multi-process ledger tests. Tests passed; CI should prefer a deliberate multiprocessing start method such as `spawn` where supported.
- The full TrainOS test suite was not run for this package.

## Important limits
The adapter only supports explicit `TRANSFER` transactions. Other transaction types are rejected until their account semantics are specified. Currency mappings and minor-unit exponents must be provided by the caller. The adapter is additive and opt-in; it does not migrate existing call sites or make the ledger production-ready for real payments.
