# TrainOS Stage 137 — Single-use retry authorization under contention

## Scope

Added a spawned-process concurrency regression test for competing retry authorizations and competing recovery starters using independent SQLite journal connections.

## Verified invariants

- When two operators concurrently authorize a failed attempt, exactly one transition to `RETRY_AUTHORIZED` succeeds; the other is rejected because the state is no longer `FAILED`.
- When two recovery starters concurrently contend for that authorization, exactly one consumes it and enters `IN_PROGRESS`; the other observes the active attempt and is blocked.
- The retry increments the attempt count and fencing token exactly once, uses a new owner run UUID, and clears one-shot authorization metadata.
- Later start/authorization calls cannot reuse the consumed authorization or alter the active journal row.

## Safety boundary

This validates transaction serialization with local SQLite and spawned processes. It does not establish distributed locking, tamper resistance, correctness on real train hardware, or safety certification.
