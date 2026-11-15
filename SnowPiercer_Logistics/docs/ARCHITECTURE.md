# Architecture
Python 3.9+ standard-library-only package. Public API in `snowpiercer_logistics/core.py`.
SQLite WAL, FULL synchronous and BEGIN IMMEDIATE serialize writes. Command receipt, domain mutation and event hash are committed in one transaction. Replaying the same key compares a SHA-256 fingerprint of canonical JSON including the principal identity.

Trust boundary: `Principal` is caller-supplied and **not authenticated**. No network service, OS credential verification, physical actuator, capacity/weight reservation, tamper-resistant anchor or distributed consensus is implemented. Hash chaining only detects some in-place edits; a privileged adversary can rewrite the whole database and recompute hashes. SQLite durability depends on filesystem and hardware guarantees.

Cargo flow: REGISTERED -> STORED -> IN_TRANSIT -> STORED (transfer) or DELIVERED. Cancellation is available from REGISTERED or STORED. Mission flow: PLANNED -> ACTIVE -> COMPLETED; cancellation from PLANNED or ACTIVE.
