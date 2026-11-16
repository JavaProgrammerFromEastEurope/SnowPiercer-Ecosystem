# TrainOS Stage 64 — Controlled checkpoint restoration

## Implemented

- Added `restore_checkpoint()` to reconstruct fresh `DiagnosticHypothesisRegistry` and `DiagnosticEvidenceTaskTracker` instances from a persisted checkpoint. Existing live instances are never mutated.
- Added pre-restoration validation of capacities, lifetime counters, assessment IDs and disposition consistency, task references, task attempt counts, global transition sequence, legal transition edges, per-task transition continuity, final state, and attempt/start counts.
- Restoration returns both newly constructed components together only after the complete checkpoint has passed integrity and domain validation.
- Tasks found `in_progress` remain `in_progress`; no automatic retry or command execution is triggered. Callers must decide how to reconcile interrupted work.
- Exported checkpoint, restore result, store, and integrity exception types through `kernel.command.events`.

## Safety and limitations

- Restore builds fresh instances and does not mutate pre-existing objects.
- The checkpoint only covers hypothesis and evidence-task state; it does not restore event history or physical equipment state.
- The hash chain detects accidental or uncoordinated edits but is not a keyed signature or substitute for access controls and independent backups.
- An in-progress task remains in progress until explicitly reconciled.

## Verification

- Focused Stage 64 tests: **8 passed**.
- Full test suite: **532 passed**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parse of all kernel Python files: **2,125 files, 0 syntax errors**.
- ZIP integrity: verified after archive creation.
