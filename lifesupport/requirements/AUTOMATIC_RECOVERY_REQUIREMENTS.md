# LIFE-CORE-013 Requirements

| ID | Requirement | Evidence |
|---|---|---|
| LIFE-CORE-013-REQ-01 | Supervisor restarts child after SIGKILL | test_supervisor_sigkill_restarts |
| LIFE-CORE-013-REQ-02 | Service reopens SQLite and serves snapshot after restart | test_supervisor_sigkill_restarts |
| LIFE-CORE-013-REQ-03 | Reject symlink socket | test_socket_symlink_denied |
| LIFE-CORE-013-REQ-04 | Reject non-socket occupant | test_regular_socket_path_denied |
| LIFE-CORE-013-REQ-05 | Preserve live socket | test_live_socket_not_unlinked |
| LIFE-CORE-013-REQ-06 | Remove verified stale socket | test_stale_socket_removed |
| LIFE-CORE-013-REQ-07 | Reject concurrent supervisor | test_second_supervisor_lock_denied |
| LIFE-CORE-013-REQ-08 | Fail closed for same-UID production clients | test_production_same_uid_denied |
| LIFE-CORE-013-REQ-09 | Reject symlink DB in production | test_production_symlink_db_denied |
| LIFE-CORE-013-REQ-10 | Reject insecure SQLite sidecars | test_production_sidecar_denied |
