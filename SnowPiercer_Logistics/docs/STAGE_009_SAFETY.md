# Safety and evidence boundaries
Verified by local regression: role denial, client-UID mismatch, one-time consumption, persistence across restart, previous API behavior.
NOT VERIFIED: distinct real UIDs, OS-enforced legacy fencing, privilege separation, immutable witness authority, independent rollback detection, adversarial filesystem access, exhaustive SIGKILL points, concurrent multi-process attack coverage, production readiness.
Threat: compromised service can falsely assert client_uid to authority. Threat: privileged adversary can roll back SQLite permit DB and anchor together. Threat: crash after consuming permit but before replying causes denial on retry (fail-closed, not availability). Threat: legacy LogisticsLedger can still be used if filesystem permissions allow it. Threat: socket and filesystem ownership require deployment-level enforcement.
Decision: BLOCKED / NO-GO. No independent E2E assurance claim.
