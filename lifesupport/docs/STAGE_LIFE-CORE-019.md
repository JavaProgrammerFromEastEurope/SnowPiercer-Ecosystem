# LIFE-CORE-019 usage

This is an **opt-in** experimental implementation, not an automatic replacement for LIFE-CORE-017. Provision a v2 hardened SQLite database, an independent 32+ byte secret, and a 0600 owner-only anchor file initialized with `RequestLedgerAnchor.initialize(db)` **offline**. The anchor must be stored in a service-owned directory. Provision the key as a service-owned regular 0600 file, outside the client-visible directory. Run `python -m lifesupport.mandatory_ledger_cli --registry REGISTRY --db DB --socket SOCKET --uids CLIENT_UID --anchor ANCHOR --key-file KEYFILE` under the dedicated non-root service UID. Use the same socket directory ownership/permissions as LIFE-CORE-016 (0711). Startup refuses untrusted recovery states before binding the socket. Existing LIFE-017 CLI remains unchanged for backward compatibility and is NOT protected by this stage.

For recovery, stop all writers, validate independent evidence, and restart only the mandatory service. It will resolve a signed pending intent if and only if the database is exactly the old snapshot or contains precisely the intended new receipt. Otherwise isolate the database and investigate; never delete the intent manually to force admission. The protocol is not guaranteed against arbitrary power interruption or joint rollback of files.

Tests: `PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -s tests -q`.

`MandatoryLedgerSupervisor(registry,db,socket_path,allowed_uids={...},anchor_path=...,key_file=...)` reuses the existing dedicated-UID supervisor for automatic child restart. The supervisor does not change UID itself and cannot restart after its own death. It requires pre-provisioned ownership, key and anchor files.
