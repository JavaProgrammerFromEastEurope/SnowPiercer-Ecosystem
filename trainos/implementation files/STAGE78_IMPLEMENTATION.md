# TrainOS Stage 78 — Externalizable event-integrity anchors

## Goal

Add a durable reference to a known command-event hash-chain head so that later verification can detect rollback, deletion, or rewriting of the event log relative to a previously recorded checkpoint.

## Changes

- Added `EventIntegrityAnchor` and `EventIntegrityAnchorStore` in `kernel/command/events/event_integrity_anchor_store.py`.
- The anchor store persists monotonically identified records in a separate SQLite database and supports creating an anchor, reading the latest anchor, listing anchors, and verifying the newest anchor against an event log.
- Added `CommandEventStore.integrity_head()` and `integrity_hash_at(sequence)` to expose the minimum read-only data required for comparison.
- Exported the new public types from `kernel.command.events`.
- Added tests for clean verification and restart persistence, payload/chain rewrite detection, deletion of an anchored tail, appending after an anchor, missing anchors, type validation, and changes to an anchored empty log.

## Verification

- Focused tests for Stages 74–78: **22 passed**.
- Full test suite: **595 passed**.
- `python -m compileall -q kernel tests`: passed.
- AST parse of Python files under `kernel`: **2,129 files, 0 syntax errors**.

## Security limits

This is a comparison checkpoint, not a tamper-proof logging system. The anchor database must be stored and access-controlled independently from the event database. If an attacker can modify both databases, they may rewrite the event log and its anchors together. For stronger guarantees, periodically export signed anchors to separately administered remote storage or immutable/WORM storage, protect signing keys outside the application host, and monitor anchor delivery failures. The current implementation does not perform remote export, cryptographic signing, or key management. It is not a safety-certified railway control component.
