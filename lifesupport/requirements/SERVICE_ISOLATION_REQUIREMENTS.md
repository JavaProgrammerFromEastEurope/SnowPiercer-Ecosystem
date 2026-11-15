# LIFE-CORE-012 requirements and verification

| ID | Requirement | Evidence |
|---|---|---|
| LIFE-SVC-001 | Reject insecure socket directory | test_insecure_dir_rejected |
| LIFE-SVC-002 | Reject socket symlinks | test_socket_symlink_rejected |
| LIFE-SVC-003 | Require peer UID match | test_different_uid_denied (Linux root) |
| LIFE-SVC-004 | Restrict socket and DB file permissions | test_permissions |
| LIFE-SVC-005 | Support read-only health | test_health |
| LIFE-SVC-006 | Support read-only state snapshot | test_snapshot |
| LIFE-SVC-007 | Reject remote write requests | test_unsupported_write |
| LIFE-SVC-008 | Recover read-only service after SIGKILL and explicit stale socket cleanup | test_sigkill_restart_sqlite_reopen |
| LIFE-SVC-009 | Serve concurrent independent clients | test_parallel_clients |
| LIFE-SVC-010 | Preserve all previous tests | full unittest discovery |
