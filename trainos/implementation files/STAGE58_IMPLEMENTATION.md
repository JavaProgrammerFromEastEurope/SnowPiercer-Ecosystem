# TrainOS Stage 58 — Diagnostic evidence collection planning

## Implemented

- Added `DiagnosticEvidenceCollectionPlanner`, a deterministic, read-only planner that translates evidence validation issues and readiness gaps into structured follow-up tasks.
- Added immutable `EvidenceCollectionTask`, `HypothesisEvidencePlan`, and `EvidenceCollectionPlan` records and exported them from `kernel.command.events`.
- Maps missing source events, incomplete history, cross-command evidence, duplicate identifiers/references, diagnostic identity mismatches, and timestamp problems to specific retrieval or review tasks.
- Identifies evidence quantity/type-diversity gaps, missing explicit assessments, open assessments, and the need for independent expert review.
- Assigns higher priority to integrity and chronology issues, with deterministic task ordering and summary counts.
- Includes five focused tests for gaps, complete-history review, integrity priority, deterministic/read-only behavior, and input contracts.

## Safety and limitations

- Tasks are recommendations only; this planner does not retrieve data, modify registry state, update assessments, or execute commands.
- Event-type diversity does not prove evidence independence. Correlation is not proof of causation.
- Missing references in an incomplete event inventory may indicate retention loss, not that an event never existed.
- This component is diagnostic support only and must not be used as a train-control or safety-interlock decision.

## Verification

- Baseline before changes: **483 passed**.
- Stage 58 focused tests: **5 passed**.
- Full suite after changes: **488 passed in 1.47s**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parsing of all **2,120** kernel Python files: **0 syntax errors**.
- ZIP integrity: checked after archive creation.
