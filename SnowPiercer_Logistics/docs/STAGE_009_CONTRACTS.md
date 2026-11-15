# Contracts
ClientBoundPermitAuthority(root, operator_uid, service_uid, timeout=1.0): context-managed Unix socket server.
client_permit_request(path, 'issue_client', scope=..., client_uid=...): operator-only -> {'permit': hex64}.
client_permit_request(path, 'consume_client', scope=..., client_uid=..., permit=...): service-only -> {'consumed': true} or AdmissionError.
ClientBoundLogisticsService(root, uid_roles, witness_socket, permit_socket, recovery_scope='logistics-recovery'): accepts legacy request(socket,'recover',{'permit': token}) shape; client UID is derived from Unix peer credentials.
Recovery returns {'recovered':true,'admission_only':true}; no physical or ledger repair occurs. Existing Stage 001–008 interfaces unchanged.
