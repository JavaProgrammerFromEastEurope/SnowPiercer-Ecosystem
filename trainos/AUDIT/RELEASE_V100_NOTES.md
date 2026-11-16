# TrainOS v100 — SQLite owner provenance and order minimization

Release status: **BLOCKED / NO-GO**. Cumulative source based on v99; no new numeric Stage.

## Confirmed root cause

The opt-in `scripts/ci/sqlite_owner_boundaries.py` instruments `sqlite3.connect` with a traced connection subclass, creation stack, explicit `close()` records, weakref finalization, `tracemalloc`, and per-test `gc.collect()`. In the strict combined probe before the fix, four connections from `tests/domains/recovery/test_recovery_assessment_snapshot.py` were garbage-collected without explicit closure. The stacks point to `CommandEventStore` and `EventIntegrityAnchorStore` allocations in two tests. Evidence: `evidence_v100/combined_probe.owners.json` and stdout.

`minimize_order_failure.py` now supports repeatable `--pytest-arg` to run the existing GC plugin. Against original v99, ddmin reduced a two-test sequence to the **single test** `test_restored_event_database_with_missing_anchor_fails_closed`, reproducing `PytestUnraisableExceptionWarning` under strict warnings and boundary GC. The same candidate in v100 did **not** reproduce the warning.

The affected test module now uses `owned_sqlite_stores` fixture with `finally` cleanup for all SQLite-backed stores, including assertion failures. Production SQLite code was not modified; evidence specifically identifies test-owned connections.

## Strict regressions

Three separate strict combined runs of `tests/domains/recovery`, `tests/domains/ci_release`, and `tests/domains/pytest_diagnostics` completed successfully: 397 PASS each, exit code 0, bounded runner verified process group absence in each run. These checks do not prove absence of all unrelated orphan processes.

A strict full suite completed with **1484 passed, 1 failed**. Failure: `tests/stage87/test_event_log_backup.py::test_existing_restore_destination_is_never_overwritten` with 23 SQLite `PytestUnraisableExceptionWarning` subexceptions. This is a separate, still-unresolved warning source; full suite remains FAIL and release NO-GO. The full suite's process group was reaped. Do not treat this as a successful full regression.

Bounded process tests (9 PASS) exercised existing real signal and residual-child contracts. Kernel Runner `_run_test` smoke: 4 PASS and 24 functional-stage registry entries. Regression selector selected and executed legacy stage 98: 2 PASS. Full Kernel Runner across all configured stages was not executed.

## Limits

- The minimized single-test failure requires diagnostic boundary `gc.collect()` and does not establish that this was the only cause of the prior order-dependent 6 warnings.
- The strict full suite still exposes 23 unraisable SQLite warnings; further owner tracing and targeted fixes are required.
- `group_absence_verified` is an OS process-group observation at runner exit, not an exhaustive proof of zero orphaned processes outside the original group.
- The owner tracer is opt-in and does not capture all possible connection factories/aliases; no warning suppression is used.
- All executed probes, logs, exit codes, and timeout/interruption evidence are retained under `AUDIT/evidence_v100/`.

## Unsuccessful diagnostics retained

A subsequent full-suite owner-provenance probe was bounded to 160 seconds and exited 124 after reaching approximately 14% of tests. The per-test `gc.collect()` and allocation stack instrumentation substantially increase runtime; this probe is **INCONCLUSIVE**, not PASS. Its stdout/stderr and exit code are preserved. The ordinary full strict run, which completed in 77.52 seconds and failed with 23 SQLite warnings, remains the authoritative full-suite result.
