# AI-CORE-013 requirements and traceability

| ID | Requirement | Implementation | Verification |
|---|---|---|---|
| AI013-R01 | Fresh DB/gateway on restart | production013.create_service | test_sigkill_restart_fresh_sqlite_and_replay |
| AI013-R02 | Enforce non-root UID and private resources | production013.create_service | cross-UID integration test |
| AI013-R03 | Cross-UID IPC without direct DB access | production013 socket group policy | test_cross_uid_access_and_file_denial |
| AI013-R04 | Reject altered trust checkpoint | gateway.verify before bind | test_fenced_checkpoint_refuses_socket_publication |
| AI013-R05 | Reject socket replacement | reclaim_stale_socket | test_socket_replacement_refused |
| AI013-R06 | Restart after SIGKILL | AdmissionSupervisor service_gid | test_supervisor_automatic_sigkill_restart |
| AI013-R07 | Reject unsafe trusted config | load_config | test_config_permissions_and_symlink_refused |
| AI013-R08 | Preserve prior library APIs | additive implementation | cumulative regression |

Unmet: atomic external checkpoint+SQLite commit, automatic authorized offline reconciliation, universal legacy import fencing, hardware trust root, production systemd integration.
