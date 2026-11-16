# TrainOS Stage 67 — Recovery-aware investigation closure

## Implemented

- `DiagnosticEvidenceTaskClosureVerifier` now emits the explicit `interrupted_task_recovery_unresolved` error finding for each `recovery_required` task. Such a task remains open and cannot be treated as completed or verified.
- `EvidenceTaskClosureReport` exposes `recovery_required_count`; `all_closed_and_verified` independently requires this count to be zero.
- `DiagnosticInvestigationClosureReporter` now reports recovery-required tasks per hypothesis and in aggregate. A hypothesis with unresolved recovery is explicitly labeled `recovery_required` and receives a recommendation to reconcile authoritative external state and record an explicit reviewed decision.
- Aggregate `open_count` includes recovery-required investigations, and `all_investigations_ready_for_expert_review` independently checks that the aggregate recovery-required count is zero.
- Added three regression tests covering task-level findings, hypothesis-level reporting, and the aggregate closure guard.

## Safety and scope

This is bookkeeping and closure gating only. It does not independently inspect external systems or verify observations. Recovery-required tasks remain unresolved until the caller performs external reconciliation and records an explicit decision through the existing task-tracker API. An investigation report marked ready for expert review is not a root-cause verdict, proof of remediation, or authorization to operate train equipment.

## Verification

- Focused tests (`tests/stage67`, `tests/stage61`, `tests/stage60`): 18 passed.
- Full-suite, compileall, AST and archive-integrity results are recorded separately in the build notes; no full-suite success is claimed unless the process exits cleanly.
