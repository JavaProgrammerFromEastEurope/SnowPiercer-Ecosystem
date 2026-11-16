# ISLAND-GEO-014 architecture, safety and operating constraints

Client UID -> service Unix socket -> service UID -> authority Unix socket -> witness UID.
Authority maintains separate witness and permit SQLite files. Client can issue a 256-bit random permit; service may consume it once. Permits are stored hashed. Admission uses existing SQLite phase journal, CAS and recovery protocol. The production service runs explicit SIGKILL injection at named IPC and transaction boundaries for testing.

**Not proven:** a permit is not bound to a specific request, local state, client attestation, expiration or transaction. A startup permit is mandatory, but a compromised service could reuse a stolen unused token, and the permit is not bound to a specific state or recovery operation; direct library recovery remains available to the service UID. Authority peer authentication is UID-only, not executable identity. Witness rollback-to-genesis cannot be reliably detected if all witness state is rolled back together with local state. Socket owner checks are vulnerable to TOCTOU unless pinned fd credentials are used. Startup does not use a global service lock and competing starts may race. OS permission deployment is required to fence legacy writers, but cannot fence root. Crash coverage excludes kernel fsync internals and some socket send boundaries. No independent end-to-end production assurance.

Safety: BLOCKED/NO-GO for production security and physical construction/operation. Do not deploy to infrastructure control.
