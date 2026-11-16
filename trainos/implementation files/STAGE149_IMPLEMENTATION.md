# TrainOS Stage 149 — concurrent journal corruption

Added a regression test for a writer/transition race in the recovery-attempt journal.
A separate SQLite connection acquires `BEGIN IMMEDIATE`, corrupts a sibling row, and
holds the transaction while another store attempts to create a new recovery attempt.
After the corrupting writer commits, the waiting transition must validate the full
journal, raise `RecoveryAttemptBlocked`, create no new row, and preserve the other
rows' ownership/fencing data. This validates the existing transaction boundary; no
production code change was needed for this scenario.

The test demonstrates SQLite write-lock serialization on the tested local database.
It is not a distributed-lock guarantee, tamper-proof storage guarantee, or train-safety
certification.
