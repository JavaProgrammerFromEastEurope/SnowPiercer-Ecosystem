# Stage 128 — Fail-Closed Handling When COMMIT Cannot Be Verified

## Scope

Added regression coverage for ambiguous SQLite COMMIT failures where the recovery journal cannot be inspected through a fresh connection. No production-code change was made because the existing resolver correctly preserves the original COMMIT exception unless every field in the expected durable row can be verified.

## Coverage

- Terminal-success transition: simulated COMMIT failure occurs before durability, and the resolver's fresh-connection path is unavailable. The operation raises the original `OperationalError`; rollback leaves the durable row `IN_PROGRESS` with its owner and fencing data intact.
- Retry authorization transition: the same failure mode leaves the durable row `FAILED`, with attempt count and fencing token unchanged and no authorization metadata written. A new attempt remains blocked until explicit authorization succeeds.
- Both cases close and reopen the journal before checking durable state.

## Verification

Focused validation: `PYTHONPATH=. pytest -q tests/stage128 tests/stage127 tests/stage126 tests/stage125` — **6 passed**. Full-suite and static checks are recorded in the release summary after execution.

## Limitations

This validates local SQLite journal behavior under injected failures. It does not prove resilience to every filesystem, storage-controller, power-loss, or distributed-host failure, and it is not safety certification for real train hardware.
