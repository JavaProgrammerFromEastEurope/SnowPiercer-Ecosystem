# Financial Ledger Contract v2 — audit notes

The v2 changes are isolated to `kernel/economy/ledger_contract/` plus its dedicated tests and documentation. The legacy transaction API remains unchanged.

Implemented in this prototype: exact compensating journal generation, one-reversal-per-original enforcement, opt-in signed balance floor, transactional floor check, SQLite and journal fingerprint verification.

Known gaps: `verify_integrity()` currently checks reversal posting counts but not a full multiset comparison of account/currency/amount with debit/credit swapped. This is explicitly a follow-up requirement before treating the report as a strong accounting control. Multiprocess identical-retry concurrency is covered by a focused test; crash injection has not yet been tested here. Full TrainOS suite was not run.

Status: `simulation-only` pending the v3 acceptance gates; not for real money.
