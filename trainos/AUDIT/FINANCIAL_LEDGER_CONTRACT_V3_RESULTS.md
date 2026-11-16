# Financial Ledger Contract v3 — validation record

## Executed checks

- `PYTHONPATH=. python -m pytest -q tests/ledger_contract`: **19 passed**.
- `python -m compileall -q kernel/economy/ledger_contract tests/ledger_contract`: **passed**.
- Multiprocess tests emitted eight Python 3.13 `DeprecationWarning` warnings because the environment uses `fork` while multithreaded. The assertions passed; CI should explicitly use a safe multiprocessing start method such as `spawn` where supported.

## New v3 coverage

- An aborted posting insert leaves no committed journal header or partial posting set.
- After reopening the database, a valid retry can commit and integrity verification passes.
- Concurrent identical reversal requests create one compensating journal.
- Reconciliation balances are grouped by account and currency.
- CSV export contains a header and deterministic operation/posting ordering.

The failure test injects a SQLite trigger abort inside the write transaction. This validates rollback semantics, but it is not equivalent to physically killing power or terminating the OS at arbitrary instruction boundaries. The reconciliation report checks internal ledger consistency; it does not reconcile against a bank, payment provider, or external settlement source. CSV output is not digitally signed and should be treated as an export, not tamper-proof evidence.

External settlement reconciliation, signed exports, authorization, chart-of-accounts semantics, tax/fee/FX, backup drills, production load and independent security/compliance review remain open. The module remains isolated from legacy TrainOS transaction APIs; no real funds or external payment provider is connected.
