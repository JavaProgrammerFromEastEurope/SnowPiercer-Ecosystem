# TrainOS Stage 76 — Persistent command event storage

## Changes
- Added `CommandEventStore`, an append-only SQLite store for immutable `CommandEvent` envelopes.
- Payloads are serialized as deterministic JSON; timestamps, event type, command ID, and event ID are persisted.
- Duplicate event IDs are idempotent only for an identical envelope; conflicting duplicates raise `ValueError`.
- `EventRegistry` accepts an optional store while preserving the in-memory default and existing bounded-history behavior. With a store configured, event reads use the durable full history rather than the in-memory cap.
- Exported `CommandEventStore` from `kernel.command.events`.

## Verification
See the Stage 76 test report in the delivered archive. SQLite persistence is application-level durability, not tamper-proof storage or a safety-certified event recorder. Payloads must be JSON-serializable.
