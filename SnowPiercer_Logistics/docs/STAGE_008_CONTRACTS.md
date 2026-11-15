# LOG-CORE-008 Contracts
- `MandatoryAdmissionLogisticsService(root, uid_roles, witness_socket, permit_socket, recovery_scope='logistics-recovery', timeout=2.0)`.
- `recover` accepts `{'permit': 64-character token}` and responds `{'recovered': true, 'admission_only': true}` on success.
- `issue_permit` is rejected on the new IPC endpoint; permits are issued by `permit_request` against independent broker.
- Fail-closed: unavailable authority, mismatched checkpoint, pending phase, invalid or replayed permit deny operation.
- Legacy `LogisticsLedger` remains callable and is not OS-fenced.
