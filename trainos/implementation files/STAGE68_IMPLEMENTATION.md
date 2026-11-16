# TrainOS Stage 68 — Evidence recovery integrity audit

## Implemented

- Added `DiagnosticEvidenceRecoveryIntegrityVerifier`, a read-only audit for task snapshots and transition history.
- Validates transition sequence, permitted state edges, task references, chain continuity, timezone-aware ISO-8601 timestamps, per-task timestamp order, actor/note audit context, current state versus latest transition, state counters, and attempt counts versus `in_progress` transitions.
- Specifically checks that a `recovery_required` task has an `in_progress -> recovery_required` history entry and that a later transition to `pending` or `blocked` carries a matching explicit `recovery decision=retry|block` note.
- Returns immutable, deterministically sorted findings; it never mutates state, repairs history, or authorizes task execution.
- Exported the verifier and report/finding types from `kernel.command.events`.
- Added seven tests in `tests/stage68/test_evidence_recovery_integrity.py`.

## Safety and scope

This verifier checks internal consistency of the supplied snapshot, not the truth of external observations. A consistent history is not proof that an external side effect did or did not occur, and it does not authorize retrying a task or controlling train equipment. Persistence checkpoint validation remains in place as a separate integrity boundary.

## Verification

- Focused regression suite: 25 passed (`tests/stage68`, `stage67`, `stage66`, `stage65`).
- Full test suite: **557 passed in 13.18 seconds**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parsing: 2,127 Python files under `kernel`, zero syntax errors.
- Archive integrity: checked after packaging.
