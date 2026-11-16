# TrainOS v90 — SQLite ownership and bounded process audit

Status: BLOCKED / NO-GO.

Changes:
- EventLogBackupManager._copy_sqlite now closes the read-only source connection if opening the destination connection raises, and closes both after backup errors.
- run_bounded_pytest now writes an atomic JSON report even after runner exceptions, retains separate stdout/stderr and legacy pytest log, uses bounded group termination and checks process-group absence. Group absence is NOT proven when the report says false (zombie or surviving descendants may be involved).
- No warning filters were suppressed; targeted tests and collection evidence are included.

Observed:
- Targeted recovery tests: 4 passed.
- Collection: 1477 tests collected.
- Three bounded strict combined attempts timed out; these are NOT PASS.
- Full strict suite bounded attempt timed out; NOT PASS.
- A prior long-running strict attempt was interrupted by execution environment; stdout is retained but no runner JSON was produced. An orphaned pytest leader was observed and explicitly killed; this is a failure of the process-lifecycle guarantee, not evidence of success.
- Tracemalloc was enabled for strict attempts, but allocation origins for remaining SQLite warnings were not established. No claim of comprehensive leak remediation.
- Kernel Runner and regression selector full compatibility not independently verified.
