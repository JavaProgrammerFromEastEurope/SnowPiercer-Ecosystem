# TrainOS Stage 138 — stale recovery owner fencing

Added a regression test proving that an earlier recovery owner cannot mutate a replacement attempt after dead-owner reconciliation, explicit retry authorization, and creation of a new fenced owner.

The test exercises stale lease renewal, stale success completion, and stale failure completion. Each operation must raise `RecoveryAttemptBlocked`, preserve the replacement row exactly, and leave the SQLite connection outside a transaction. The old owner UUID is retained for the stale requests while the replacement receives a new UUID and incremented fencing token.

No production code changed: the existing owner UUID/fencing-token checks reject these stale operations in the local SQLite journal. This is a regression test, not evidence of distributed locking, tamper resistance, or real-train safety certification.
