# Contracts — Stage 013

`run_as_uid(uid, script, *args, timeout=5) -> dict`: root-only child process;
returns uid, returncode, bounded stdout/stderr. Never executes privileged writes.
`assert_kernel_uid(uid) -> True`: fails closed if child identity differs.
`assert_legacy_fenced(path, denied_uids) -> list`: proves denial for named UIDs only.
`accept_peer_uid(listener) -> int`: kernel-derived identity of a direct AF_UNIX peer.
`verify_cross_uid_policy(IsolationPolicy) -> True`: requires root and real UID probes.
`mandatory_production_entrypoint(...)`: always raises AdmissionError.

All Stage 001–012 public signatures unchanged. Linux/POSIX root required for probes.
