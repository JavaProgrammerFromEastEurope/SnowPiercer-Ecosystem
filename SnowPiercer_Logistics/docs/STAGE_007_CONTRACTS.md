# LOG-CORE-007 Contracts
`RecoveryPermitAuthority(root, operator_uid, service_uid, timeout=1.0)` context manager.
`permit_request(path, 'issue', scope=..., target_uid=...) -> {'permit': token}`.
`permit_request(path, 'consume', scope=..., permit=...) -> {'consumed': True}`.
`recover_with_authority(root, witness_socket, permit_socket, permit=..., uid=...)` consumes broker permit before calling legacy recovery.
Errors fail closed via `AdmissionError`. Network protocol: newline-delimited JSON, max 8192 bytes request. Existing `recover_after_witness_cas` remains callable for compatibility, therefore mandatory fencing is not achieved.
