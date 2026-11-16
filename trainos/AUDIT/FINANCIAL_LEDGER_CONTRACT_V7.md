# Financial Ledger Contract v7 — Recovery and process-safety verification

## Scope

This stage hardens restore publication semantics and validates the isolated ledger under Python's `spawn` multiprocessing start method. It does not integrate the ledger with real payments or alter the legacy `TransactionEngine` API.

## Changes

- Multiprocess idempotency and reversal tests explicitly use `multiprocessing.get_context("spawn")`, avoiding implicit `fork` and its interaction with multithreaded test runners.
- Restore with `overwrite=False` now publishes the validated staging file with an atomic hard-link operation. This is a no-clobber publication step: if another process creates the destination after the initial existence check, restore fails instead of replacing that file.
- Restore with `overwrite=True` retains explicit replacement semantics via `os.replace`.
- New tests cover unsupported schema versions, explicit overwrite, restored account policy enforcement, reversal-link integrity, and destination no-clobber behavior.

## Verification performed

- `PYTHONPATH=. python -m pytest -q tests/ledger_contract`: **44 passed**.
- `PYTHONPATH=. python -m pytest -q tests/stage172 tests/stage173 tests/stage174 tests/stage175 tests/stage176 tests/stage177`: **15 passed**.
- Combined targeted scope: **59 passed** across the two runs.
- `compileall` and whole-tree Python AST parse are recorded in the build manifest.

## Boundaries and limitations

- The full TrainOS test suite was not run.
- The tests verify process-level SQLite serialization and restore semantics, not power-loss durability across every filesystem/hardware combination.
- The hard-link no-clobber path assumes temporary and destination files are on the same filesystem; they are created in the destination directory for this reason. Filesystems or policies that disallow hard links will fail closed rather than silently overwrite.
- Restore should be performed with application writers stopped. WAL sidecar handling, encrypted/off-site backups, retention, signed checkpoints and operational disaster-recovery drills remain separate work.
- Fingerprints detect consistency failures but are not an external authenticity mechanism.
- No production payment use is authorized by this stage.

## Status

`spawn`-based targeted concurrency/recovery checks pass. The financial ledger remains an isolated prototype; it is not production-ready and is not connected to SnowPiercer customer payments.
