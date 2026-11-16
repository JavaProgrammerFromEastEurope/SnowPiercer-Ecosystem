# TrainOS Stage 86 — Consistent recovery assessment

## Problem
`EventLogRecoveryGate.assess()` previously verified the anchor, read the event-log head, and read the latest anchor in separate calls. Concurrent appends or anchor updates could make the returned assessment combine evidence from different moments.

## Changes
- `EventIntegrityAnchorStore.verify_against()` can consume a captured `EventIntegrityAnchor` and `CommandEventStore.integrity_snapshot()` without re-reading either source.
- `EventLogRecoveryGate.assess()` reads the latest anchor once and obtains one atomic event-log snapshot. Its findings, event sequence, and anchor sequence are derived from those captured values.
- Added regression tests for single-snapshot use, fail-closed behavior when a restored database has no anchor, detection of rollback to an older event database while retaining the anchor store, and reporting the snapshot head despite a later append.

## Validation
Run from the project root:

```bash
PYTHONPATH=. pytest -q tests/stage86
PYTHONPATH=. pytest -q
python -m compileall -q kernel tests
```

## Limitations
The event database and anchor database are separate stores, so they cannot be made one atomic cross-database transaction by this change. The assessment uses one captured anchor and one event snapshot, but a separately controlled remote/WORM anchor remains important for resisting privileged tampering. This is application integrity logic, not safety certification.
