# TrainOS Stage 136 — Concurrent dead-owner reconciliation

## Scope

Added a spawned-process race regression test for two independent SQLite journal clients that simultaneously observe an `IN_PROGRESS` attempt whose recorded process has exited.

## Verified behavior

- SQLite `BEGIN IMMEDIATE` serializes reconciliation of the same attempt key.
- Exactly one contender changes the abandoned attempt to `FAILED`; the other observes the failed state and is told that explicit retry authorization is required.
- Neither contender starts a replacement attempt during reconciliation.
- The failed row retains the original run UUID and fencing token for forensic traceability while clearing PID and lease ownership fields.
- A new attempt can begin only after explicit retry authorization; the next attempt increments both attempt count and fencing token.

## Safety boundary

The test uses a simulated dead PID and local SQLite. PID liveness is a same-host heuristic and is not a distributed lock, protection against PID reuse, or evidence of real-train safety certification.
