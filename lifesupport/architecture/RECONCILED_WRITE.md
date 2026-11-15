# Supervised production write and request reconciliation

The pre-provisioned Linux service UID owns a private 0700 SQLite directory and a 0711 socket directory. Clients are authorized by SO_PEERCRED; they cannot directly open the DB under the tested DAC policy. ProductionWriteSupervisor launches reconciled_write_cli under the same already-unprivileged UID, validates connected server UID/PID and restarts it after failure.

ReconciledWriteService is an opt-in subclass of ProductionWriteService; the Stage-016 handler remains unchanged except for a dispatch method allowing specialization. `life_request_receipts` stores request_id, SHA-256 of canonical request and authenticated UID, event sequence, and event_id. The event and receipt INSERT occur in one BEGIN IMMEDIATE transaction and share one COMMIT. A committed retry returns replayed=true. A different request or UID with the same request_id is rejected.

The coordination lease is acquired in a separate transaction and expires after two seconds if the process is killed. An immediate retry before expiry can be rejected; the client must retry later with the same request_id. A read-only receipt lookup can establish whether the event committed. SQLite COMMIT is the logical linearization point; lost IPC responses do not imply rollback.

This does NOT provide hardware actuation, distributed consensus, power-loss proof, protection against root/service UID, or a global exactly-once guarantee across independently replaced databases.
