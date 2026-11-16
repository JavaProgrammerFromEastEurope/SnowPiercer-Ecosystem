# TrainOS v96 — BLOCKED/NO-GO

Based on cumulative v95. Updated order minimizer to use isolated process groups, bounded termination, separate stdout/stderr and v2 evidence. Added optional pytest GC-boundary probe (`scripts/ci/sqlite_gc_probe.py`) for diagnostic use only; it does not suppress warnings.

Strict targeted tests: 6 PASS. Initial real combined order probe timed out, so no minimal reproducer established. Three combined attempts and full suite were attempted, without confirmed successful completion. Production SQLite code unchanged: no verified root cause was isolated. See validation JSON and evidence files for each run.

Do not claim all orphan processes absent: process groups were checked per runner only, and an externally interrupted invocation required manual cleanup. Kernel Runner not validated.
