# TrainOS v98 — process lifecycle diagnostics

Status: BLOCKED / NO-GO.

Added optional pytest lifecycle journal (`scripts/ci/pytest_lifecycle_probe.py`) with fsync on each event, to identify last started/finished nodeid even when pytest is killed. No warning filters or SQLite behavior changes.

The combined run observed failure marker F and was externally interrupted. Its event journal identifies last started test; it does not establish SQLite ownership or a minimal reproducer. Nested pytest subprocesses and orphan cleanup remain unproven.

Verified: 5 process contracts PASS, 1 lifecycle contract PASS. Three strict combined regressions and full strict suite NOT CONFIRMED.
