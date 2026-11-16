# TrainOS Stage 150 — SQLite COMMIT fault recovery

This stage adds focused fault-injection coverage for two distinct outcomes at the SQLite COMMIT boundary:

1. A simulated storage I/O error raised before SQLite receives COMMIT. The store must roll back, preserve the durable `IN_PROGRESS` row and fencing metadata, close the transaction, and permit a later explicit completion.
2. A simulated lost acknowledgement after SQLite durably commits. The store must resolve the ambiguous outcome from the durable full-row snapshot, return the committed `SUCCEEDED` state, and reject a duplicate completion without changing the attempt count.

These are deterministic injected faults, not a claim that a physical disk failure or power loss was reproduced. Existing crash/restart and verification-outage tests continue to cover those adjacent cases.
