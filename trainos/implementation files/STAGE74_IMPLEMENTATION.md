# TrainOS Stage 74 — cross-snapshot reference integrity

## Scope

Audited the existing checkpoint serializer/validator before making changes. The checkpoint already validates that task and assessment hypothesis references exist, that task transition history is continuous, and that state counters agree. This stage adds the missing cross-snapshot task-identity check without introducing a parallel audit subsystem.

## Changes

- `DiagnosticInvestigationCheckpointService._validate_snapshots()` now verifies that every task definition is an `EvidenceCollectionTask` and that its stable ID matches the existing tracker contract: `<hypothesis_id>::<task.code>`.
- Task evidence event references must be a tuple of non-empty strings without duplicates.
- Validation happens before persistence and during checkpoint decoding, so invalid cross-snapshot data is rejected instead of being committed or restored.
- No data is silently rewritten and no external task is executed.
- Added `tests/stage74/test_checkpoint_cross_snapshot_links.py` covering invalid task identity, duplicate evidence references, and a valid round trip.

## Verification

- Focused stages 71–74: **11 passed**.
- Full suite: **576 passed in 2.96s**, pytest exited successfully.
- `compileall` for `kernel` and `tests`: passed.
- AST parse of all kernel Python files: 0 syntax errors.
- ZIP integrity check: passed.

## Limits

This validates references within the saved checkpoint. It cannot establish that referenced event IDs exist in an external authoritative event store because that store is not part of this checkpoint contract. It is not a safety certification or permission to control physical train equipment.
