# TrainOS Stage 69 — Structured checkpoint restore assessment

## Implemented

- Added immutable `CheckpointRestoreAssessment`, a structured result for checkpoint restoration.
- Added `DiagnosticInvestigationCheckpointService.restore_checkpoint_with_assessment()`.
- A successful restore includes the read-only `DiagnosticEvidenceRecoveryIntegrityVerifier` report.
- Missing checkpoints return `checkpoint_not_found`; invalid persisted checkpoint schemas return `checkpoint_integrity_rejected`; invalid payload/domain data returns `checkpoint_payload_invalid`.
- Invalid checkpoints never return partially restored registry/tracker instances. No checkpoint is repaired, and no task is retried or considered externally safe based on local state alone.
- Exported the assessment result from `kernel.command.events`.
- Added four tests covering valid restore/report, missing checkpoint, invalid schema and blank-ID input validation.

## Verification

- Focused Stage 69 + Stage 68 + Stage 63 tests: **16 passed**.
- `python3 -m compileall -q kernel tests`: passed.
- AST parse of the three changed Python files: passed.
- Full suite attempt: pytest progressed to approximately 64% before the 240-second execution limit; it did not complete, so this is not reported as a passing full-suite run.
- ZIP archive integrity check performed after packaging.

## Safety scope

The assessment reports internal checkpoint and task-history integrity only. It does not validate the truth of external observations, authorize retrying external side effects, or make TrainOS suitable for controlling real train hardware.
