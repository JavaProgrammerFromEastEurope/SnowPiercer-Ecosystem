# TrainOS Stage 85 — Atomic integrity snapshots for anchors

## Scope

Ensure that event-chain verification, the current chain head, and the hashes used to
compare a persistent anchor are observed from one SQLite read snapshot.

## Changes

- Added `CommandEventStore.integrity_snapshot()`, returning integrity findings, the
  chain head, and sequence-to-hash references from a single read transaction.
- Updated `EventIntegrityAnchorStore.create_anchor()` to validate and select the head
  through the atomic snapshot API instead of separate reads.
- Updated `EventIntegrityAnchorStore.verify_against()` to compare the anchor against
  a single event-store snapshot, avoiding mixed results across separate event DB reads.
- Added tests for snapshot consistency, anchor creation/verification integration, and
  transaction rollback when auditing fails.

## Limitations

- The event store and anchor store are separate SQLite databases; this is not a single
  cross-database atomic transaction. The anchor DB must be independently protected.
- An attacker able to rewrite both the event DB and trusted anchor DB can still forge
  local state. Use independently controlled remote/WORM storage or externally held
  signing keys for stronger trust.
- This is application-level integrity checking, not a safety-certified control system.
