# AI-CORE-018 — Deterministic Crash Injection & Cold Recovery Regression Stabilization

Status: PARTIAL / safety-critical NO-GO.

Implemented: explicit test-only SIGKILL injector for six phase boundaries; cold recovery when checkpoint was already durably updated; non-crash replay rejection clears PREPARED only after trusted gateway verification. Existing production IPC continues to use JournaledAdmissionGateway. Legacy Python library imports remain possible.

Crash points: after_prepare, before_sqlite_commit (SQLite trace callback at COMMIT), after_sqlite_commit, before_checkpoint, after_checkpoint, before_clean. The after_sqlite_commit and before_checkpoint hooks are adjacent, not two distinct persistent writes. The hook is process-local, explicitly enabled, and NOT supported for concurrent admission.

Observed: root-capable Linux UID fixture exercised all six SIGKILL cases, offline recovery, IPC restart and replay behavior in a focused run. No hardware monotonic root, no defense against privileged coherent rollback, no proof of universal legacy library write fencing. Operator_verified remains an unverified caller assertion. Full cumulative regression did not complete; do not claim success.

The recovery path does not establish atomicity of SQLite, checkpoint, and phase journal. A PREPARED journal fences IPC until offline authorization. No production deployment authorization is implied.
