# Financial Ledger Contract v2 — verification results

Executed in the canonical TrainOS tree with Python 3.13 and pytest 9.0.2.

- `PYTHONPATH=. python -m pytest -q tests/ledger_contract`: **16 passed**.
- Focused ledger + currency/transaction/economic audit + consumption tests: **32 passed**.
- Four multiprocessing fork deprecation warnings were emitted by Python because the pytest parent process is multithreaded; the test passed, but CI should switch to an explicit `spawn` multiprocessing context to remove ambiguity.
- The full TrainOS suite was not run. No production/security qualification was performed.

The v2 additions remain an isolated prototype. Account balance floors are opt-in; reversals are exact full compensations; integrity verification checks fingerprints and exact reversal postings. Crash-injection testing, backup/restore drills, load testing, access controls, provider integration, legal/compliance review, and production-scale qualification remain outstanding.
