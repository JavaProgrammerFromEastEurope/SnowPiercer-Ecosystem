# Stage 107 — Recovery Process Crash Injection

## Scope

Added subprocess-based crash-injection regression tests at three durable recovery boundaries. Child processes use independent SQLite connections and `os._exit()` so normal Python `finally` blocks and connection cleanup do not run.

## Scenarios

1. **Crash before publication:** no candidate is created; journal remains `IN_PROGRESS`. A subsequent startup does not silently retry. The interrupted attempt must be transitioned to `FAILED` and receive explicit retry authorization before a new attempt can run.
2. **Crash after candidate publication but before journal commit:** candidate remains on disk and journal remains `IN_PROGRESS`. A later process independently verifies the backup and candidate against the anchor and reconciles the journal to `SUCCEEDED`.
3. **Crash after durable success commit but before return:** journal remains `SUCCEEDED`; a later startup independently verifies and reuses the candidate rather than publishing again.

## Verification

Run `PYTHONPATH=. pytest -q tests/stage107` and the full `PYTHONPATH=. pytest -q` suite. These tests exercise local filesystem and SQLite crash windows; they do not establish power-loss durability on every filesystem, distributed ownership, or transport safety certification.
