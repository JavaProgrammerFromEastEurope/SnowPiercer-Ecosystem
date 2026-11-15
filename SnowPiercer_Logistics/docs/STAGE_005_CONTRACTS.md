# LOG-CORE-005 contracts

`WitnessAuthority(root, service_uid).start()/stop()`; `witness_request(socket_path, action, before=None, after=None, timeout=1.0)` where `action` is `read` or `cas`. CAS succeeds only when `before` equals stored state, and the new event count increases by exactly one; genesis initializes at zero. `WitnessBackedLogisticsService(root, uid_roles, witness_socket, timeout=2.0)` inherits existing IPC commands. All witness errors are fail-closed. CAS and local checkpoint are NOT a single atomic transaction.
