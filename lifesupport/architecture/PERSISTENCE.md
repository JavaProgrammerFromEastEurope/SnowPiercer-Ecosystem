# LIFE-CORE-004 — Persistent Lifecycle & Recovery

The prior `Lifecycle` API remains unchanged. `PersistentLifecycle(registry, path)` wraps it in a SQLite journal, verifies the registry fingerprint and replays the full event history at startup. Each transition begins `BEGIN IMMEDIATE`, replays committed records, checks lifecycle invariants, writes a canonical JSON event and commits before updating the exposed in-memory lifecycle. Concurrent instances serialize at the SQLite writer lock; each write replays the latest committed history. WAL and synchronous=FULL are requested.

## Recovery policy

Recovery is fail-closed: invalid JSON, broken hashes, invalid sequence, event-ID mismatch, illegal transition or registry mismatch prevents opening the journal. No automatic truncation or repair. Operators must preserve the original DB and WAL files for forensic analysis and recover from independently verified backups. `recover()` refreshes in-memory state under the writer lock.

## Scope and limitations

This is an offline *logical* lifecycle model only. It does not operate physical life-support equipment. SHA-256 is not an authentication mechanism. A malicious actor able to rewrite the entire database and recompute the chain can forge history; deletion of the final events cannot be detected without an external trusted head or independent replication. No authenticated principals, authorization, secure time, distributed consensus, hardware health attestation, backup scheduler, or remote TrainOS integration. Power-loss durability depends on operating system, filesystem and storage device behavior; no hardware fault-injection testing has been performed. Registry fingerprint is based on the loaded data and does not authenticate that data.

The SQLite connection is not designed to be shared across threads. A single `PersistentLifecycle` instance is owned by one thread; separate processes/connections may serialize writes. Close all connections before filesystem backup or use the SQLite online backup API.
