# LOG-CORE-019 Contracts

TransactionAdmissionService._assert_endpoints(): requires two distinct, existing Unix socket filesystem nodes, neither world writable nor symlinks. Does not verify remote server identity or kernel peer UID. _dispatch(): rejects legacy issue_permit and inconsistent transaction snapshots; delegates all other requests to inherited API. inspect_transaction(service): read-only snapshot of recovery decision. production_admission(): always raises AdmissionError.
