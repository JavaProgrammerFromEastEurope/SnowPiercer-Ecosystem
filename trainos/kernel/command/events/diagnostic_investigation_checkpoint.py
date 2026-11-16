from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .diagnostic_evidence_collection_planner import EvidenceCollectionTask
from .diagnostic_evidence_task_tracker import (
    DiagnosticEvidenceTaskTracker,
    EvidenceTaskTrackerSnapshot,
    EvidenceTaskTransition,
    TrackedEvidenceTask,
)
from .diagnostic_hypothesis_registry import (
    DiagnosticHypothesis,
    DiagnosticHypothesisRegistry,
    HypothesisAssessment,
    HypothesisRegistrySnapshot,
)
from .diagnostic_evidence_recovery_integrity import (
    DiagnosticEvidenceRecoveryIntegrityVerifier,
    EvidenceRecoveryIntegrityFinding,
    EvidenceRecoveryIntegrityReport,
)
from .diagnostic_investigation_store import (
    DiagnosticInvestigationStore,
    InvestigationStoreIntegrityError,
    StoredInvestigationRecord,
)


@dataclass(frozen=True, slots=True)
class RestoredDiagnosticInvestigation:
    """Fresh domain instances reconstructed from a fully validated checkpoint."""

    checkpoint: "DiagnosticInvestigationCheckpoint"
    hypothesis_registry: DiagnosticHypothesisRegistry
    task_tracker: DiagnosticEvidenceTaskTracker


@dataclass(frozen=True, slots=True)
class CheckpointRestoreAssessment:
    """Structured outcome of a checkpoint restore attempt.

    A failed assessment never exposes partially restored domain objects. The error
    message is diagnostic context only; callers must not treat a failed restore as
    an empty investigation.
    """

    checkpoint_id: str
    restored: RestoredDiagnosticInvestigation | None
    integrity_report: EvidenceRecoveryIntegrityReport | None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def is_successful(self) -> bool:
        return self.restored is not None and self.error_code is None and (
            self.integrity_report is None or self.integrity_report.is_consistent
        )


@dataclass(frozen=True, slots=True)
class DiagnosticInvestigationCheckpoint:
    """Consistent, persisted view of hypothesis and evidence-task state."""

    checkpoint_id: str
    revision: int
    hypotheses: HypothesisRegistrySnapshot
    tasks: EvidenceTaskTrackerSnapshot
    checksum: str
    created_at_iso: str


class DiagnosticInvestigationCheckpointService:
    """Persist and restore registry/tracker snapshots as one atomic record.

    The service deliberately checkpoints immutable snapshots rather than mutating or
    pretending to hydrate the original in-memory registry/tracker instances. A single
    underlying record keeps both snapshots at the same checkpoint revision.
    """

    RECORD_TYPE = "diagnostic_investigation_checkpoint"
    SCHEMA_VERSION = 1

    def __init__(self, store: DiagnosticInvestigationStore) -> None:
        if not isinstance(store, DiagnosticInvestigationStore):
            raise TypeError("store must be a DiagnosticInvestigationStore")
        self._store = store

    @staticmethod
    def _serialize_hypotheses(snapshot: HypothesisRegistrySnapshot) -> dict[str, Any]:
        if not isinstance(snapshot, HypothesisRegistrySnapshot):
            raise TypeError("hypotheses must be a HypothesisRegistrySnapshot")
        return {
            "hypotheses": [asdict(item) for item in snapshot.hypotheses],
            "assessments": [asdict(item) for item in snapshot.assessments],
            "total_registered": snapshot.total_registered,
            "total_assessments": snapshot.total_assessments,
        }

    @staticmethod
    def _serialize_tasks(snapshot: EvidenceTaskTrackerSnapshot) -> dict[str, Any]:
        if not isinstance(snapshot, EvidenceTaskTrackerSnapshot):
            raise TypeError("tasks must be an EvidenceTaskTrackerSnapshot")
        return {
            "tasks": [asdict(item) for item in snapshot.tasks],
            "transitions": [asdict(item) for item in snapshot.transitions],
            "total_registered": snapshot.total_registered,
            "total_transitions": snapshot.total_transitions,
            "pending_count": snapshot.pending_count,
            "in_progress_count": snapshot.in_progress_count,
            "completed_count": snapshot.completed_count,
            "blocked_count": snapshot.blocked_count,
            "recovery_required_count": snapshot.recovery_required_count,
        }

    def save_checkpoint(
        self,
        checkpoint_id: str,
        hypotheses: HypothesisRegistrySnapshot,
        tasks: EvidenceTaskTrackerSnapshot,
        *,
        expected_revision: int = 0,
    ) -> DiagnosticInvestigationCheckpoint:
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise ValueError("checkpoint_id must be a non-empty string")
        # Validate cross-snapshot references before writing anything, so invalid checkpoints
        # cannot be committed and then fail to reload.
        self._validate_snapshots(hypotheses, tasks)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "hypotheses": self._serialize_hypotheses(hypotheses),
            "tasks": self._serialize_tasks(tasks),
        }
        record = self._store.save(
            self.RECORD_TYPE, checkpoint_id.strip(), payload,
            expected_revision=expected_revision,
        )
        return self._decode_record(record)

    def restore_checkpoint(
        self, checkpoint_id: str, *, max_hypotheses: int = 1000,
        max_tasks: int = 5000, max_attempts: int = 3,
    ) -> RestoredDiagnosticInvestigation | None:
        """Reconstruct fresh domain instances only after validating the whole checkpoint.

        Existing instances are never mutated. If validation or reconstruction fails, no
        partially restored registry/tracker is returned and no persisted data is changed.
        Tasks that were in progress remain in that state; this method never retries them.
        """
        checkpoint = self.load_checkpoint(checkpoint_id)
        if checkpoint is None:
            return None
        self._validate_restorable(checkpoint, max_hypotheses, max_tasks, max_attempts)

        registry = DiagnosticHypothesisRegistry(max_hypotheses=max_hypotheses)
        tracker = DiagnosticEvidenceTaskTracker(max_tasks=max_tasks, max_attempts=max_attempts)
        # Seed private state only on new, unpublished instances. All invariants are checked
        # before these assignments; callers receive both objects together on success.
        registry._hypotheses = {item.hypothesis_id: item for item in checkpoint.hypotheses.hypotheses}
        registry._assessments = list(checkpoint.hypotheses.assessments)
        registry._total_registered = checkpoint.hypotheses.total_registered
        registry._total_assessments = checkpoint.hypotheses.total_assessments
        registry._next_assessment_id = max(
            checkpoint.hypotheses.total_assessments,
            max((item.assessment_id for item in checkpoint.hypotheses.assessments), default=0),
        ) + 1

        tracker._tasks = {item.task_id: item for item in checkpoint.tasks.tasks}
        tracker._transitions = list(checkpoint.tasks.transitions)
        tracker._total_registered = checkpoint.tasks.total_registered
        tracker._total_transitions = checkpoint.tasks.total_transitions
        return RestoredDiagnosticInvestigation(checkpoint, registry, tracker)

    def restore_checkpoint_with_assessment(
        self, checkpoint_id: str, *, max_hypotheses: int = 1000,
        max_tasks: int = 5000, max_attempts: int = 3,
    ) -> CheckpointRestoreAssessment:
        """Restore a checkpoint and return structured diagnostics on failure.

        This is a convenience boundary for callers that need an auditable result
        instead of exception-only control flow. It does not repair invalid data or
        infer that external task side effects are safe to repeat.
        """
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise ValueError("checkpoint_id must be a non-empty string")
        normalized_id = checkpoint_id.strip()
        try:
            restored = self.restore_checkpoint(
                normalized_id, max_hypotheses=max_hypotheses,
                max_tasks=max_tasks, max_attempts=max_attempts,
            )
        except InvestigationStoreIntegrityError as exc:
            return CheckpointRestoreAssessment(
                checkpoint_id=normalized_id, restored=None, integrity_report=None,
                error_code="checkpoint_integrity_rejected", error_message=str(exc),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return CheckpointRestoreAssessment(
                checkpoint_id=normalized_id, restored=None, integrity_report=None,
                error_code="checkpoint_payload_invalid", error_message=str(exc),
            )
        if restored is None:
            return CheckpointRestoreAssessment(
                checkpoint_id=normalized_id, restored=None, integrity_report=None,
                error_code="checkpoint_not_found", error_message="No checkpoint exists for this ID.",
            )
        report = DiagnosticEvidenceRecoveryIntegrityVerifier().verify(restored.checkpoint.tasks)
        if not report.is_consistent:
            return CheckpointRestoreAssessment(
                checkpoint_id=normalized_id, restored=None, integrity_report=report,
                error_code="task_recovery_history_inconsistent",
                error_message="Checkpoint task history failed the recovery integrity audit.",
            )
        return CheckpointRestoreAssessment(
            checkpoint_id=normalized_id, restored=restored, integrity_report=report,
        )

    @classmethod
    def _validate_restorable(
        cls, checkpoint: DiagnosticInvestigationCheckpoint,
        max_hypotheses: int, max_tasks: int, max_attempts: int,
    ) -> None:
        cls._validate_snapshots(checkpoint.hypotheses, checkpoint.tasks)
        for value, name in ((max_hypotheses, "max_hypotheses"), (max_tasks, "max_tasks"),
                            (max_attempts, "max_attempts")):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        hs, ts = checkpoint.hypotheses, checkpoint.tasks
        if len(hs.hypotheses) > max_hypotheses or len(ts.tasks) > max_tasks or any(
            item.max_attempts > max_attempts for item in ts.tasks
        ):
            raise InvestigationStoreIntegrityError("checkpoint exceeds configured restore capacity")
        if hs.total_registered < len(hs.hypotheses) or hs.total_assessments < len(hs.assessments):
            raise InvestigationStoreIntegrityError("checkpoint lifetime counters are below retained records")

        dispositions = {"under_review", "evidence_supports", "evidence_refutes", "insufficient_evidence"}
        hypotheses = {item.hypothesis_id: item for item in hs.hypotheses}
        if any(item.disposition not in dispositions for item in hs.hypotheses):
            raise InvestigationStoreIntegrityError("checkpoint contains an invalid hypothesis disposition")
        assessment_ids = [item.assessment_id for item in hs.assessments]
        if any(isinstance(i, bool) or not isinstance(i, int) or i < 1 for i in assessment_ids) or len(set(assessment_ids)) != len(assessment_ids):
            raise InvestigationStoreIntegrityError("checkpoint contains invalid or duplicate assessment IDs")
        if assessment_ids != sorted(assessment_ids):
            raise InvestigationStoreIntegrityError("checkpoint assessment history is not ordered")
        latest_assessment = {}
        for item in hs.assessments:
            if item.disposition not in dispositions or not item.evidence_event_ids or not item.reviewer.strip() or not item.rationale.strip():
                raise InvestigationStoreIntegrityError("checkpoint contains an invalid assessment")
            latest_assessment[item.hypothesis_id] = item.disposition
        for hypothesis_id, disposition in latest_assessment.items():
            if hypotheses[hypothesis_id].disposition != disposition:
                raise InvestigationStoreIntegrityError("hypothesis disposition disagrees with its latest assessment")

        task_by_id = {item.task_id: item for item in ts.tasks}
        allowed_transitions = {(None, "pending"), ("pending", "in_progress"),
                               ("pending", "blocked"), ("in_progress", "completed"),
                               ("in_progress", "pending"), ("in_progress", "blocked"),
                               ("in_progress", "recovery_required"), ("recovery_required", "pending"),
                               ("recovery_required", "blocked")}
        if ts.total_registered < len(ts.tasks) or ts.total_transitions != len(ts.transitions):
            raise InvestigationStoreIntegrityError("checkpoint task counters disagree with retained history")
        sequences = [item.sequence for item in ts.transitions]
        if sequences != list(range(1, ts.total_transitions + 1)):
            raise InvestigationStoreIntegrityError("checkpoint transition sequence has gaps or duplicates")
        current_state = {}
        start_counts = {}
        for transition in ts.transitions:
            if transition.task_id not in task_by_id or (transition.from_state, transition.to_state) not in allowed_transitions:
                raise InvestigationStoreIntegrityError("checkpoint contains an invalid task transition")
            if not transition.actor.strip() or not transition.note.strip():
                raise InvestigationStoreIntegrityError("checkpoint transition is missing actor or note")
            if transition.task_id in current_state and transition.from_state != current_state[transition.task_id]:
                raise InvestigationStoreIntegrityError("checkpoint task transition chain is discontinuous")
            if transition.task_id not in current_state and transition.from_state is not None:
                raise InvestigationStoreIntegrityError("checkpoint task history lacks its initial transition")
            current_state[transition.task_id] = transition.to_state
            if transition.to_state == "in_progress":
                start_counts[transition.task_id] = start_counts.get(transition.task_id, 0) + 1
        for task_id, task in task_by_id.items():
            if task.state not in {"pending", "in_progress", "completed", "blocked", "recovery_required"}:
                raise InvestigationStoreIntegrityError("checkpoint contains an invalid task state")
            if (isinstance(task.attempts, bool) or not isinstance(task.attempts, int) or task.attempts < 0
                    or isinstance(task.max_attempts, bool) or not isinstance(task.max_attempts, int)
                    or task.max_attempts < 1 or task.attempts > task.max_attempts or task.max_attempts > max_attempts):
                raise InvestigationStoreIntegrityError("checkpoint contains invalid task attempt counts")
            if current_state.get(task_id) != task.state:
                raise InvestigationStoreIntegrityError("checkpoint task state disagrees with transition history")
            if start_counts.get(task_id, 0) != task.attempts:
                raise InvestigationStoreIntegrityError("checkpoint task attempts disagree with transition history")

    def load_checkpoint(self, checkpoint_id: str) -> DiagnosticInvestigationCheckpoint | None:
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise ValueError("checkpoint_id must be a non-empty string")
        record = self._store.load(self.RECORD_TYPE, checkpoint_id.strip())
        return None if record is None else self._decode_record(record)

    @classmethod
    def _decode_record(cls, record: StoredInvestigationRecord) -> DiagnosticInvestigationCheckpoint:
        payload = record.payload
        if payload.get("schema_version") != cls.SCHEMA_VERSION:
            raise InvestigationStoreIntegrityError("unsupported investigation checkpoint schema version")
        raw_h = payload.get("hypotheses")
        raw_t = payload.get("tasks")
        if not isinstance(raw_h, dict) or not isinstance(raw_t, dict):
            raise InvestigationStoreIntegrityError("checkpoint is missing hypothesis or task snapshot")
        try:
            hypotheses = tuple(DiagnosticHypothesis(
                hypothesis_id=item["hypothesis_id"], diagnostic_event_id=item["diagnostic_event_id"],
                command_id=item["command_id"], diagnostic_code=item["diagnostic_code"],
                pattern_code=item["pattern_code"], observed_event_types=tuple(item["observed_event_types"]),
                evidence_note=item["evidence_note"], analyzer_confidence=item["analyzer_confidence"],
                disposition=item["disposition"],
            ) for item in raw_h["hypotheses"])
            assessments = tuple(HypothesisAssessment(
                assessment_id=item["assessment_id"], hypothesis_id=item["hypothesis_id"],
                disposition=item["disposition"], evidence_event_ids=tuple(item["evidence_event_ids"]),
                reviewer=item["reviewer"], rationale=item["rationale"], assessed_at_iso=item["assessed_at_iso"],
            ) for item in raw_h["assessments"])
            hypothesis_snapshot = HypothesisRegistrySnapshot(
                hypotheses=hypotheses, assessments=assessments,
                total_registered=raw_h["total_registered"], total_assessments=raw_h["total_assessments"],
            )
            tracked_tasks = []
            for item in raw_t["tasks"]:
                task = EvidenceCollectionTask(**item["task"])
                tracked_tasks.append(TrackedEvidenceTask(
                    task_id=item["task_id"], hypothesis_id=item["hypothesis_id"], task=task,
                    state=item["state"], attempts=item["attempts"], max_attempts=item["max_attempts"],
                    result_note=item["result_note"], evidence_event_ids=tuple(item["evidence_event_ids"]),
                    updated_at_iso=item["updated_at_iso"],
                ))
            transitions = tuple(EvidenceTaskTransition(
                sequence=item["sequence"], task_id=item["task_id"], from_state=item["from_state"],
                to_state=item["to_state"], actor=item["actor"], note=item["note"],
                timestamp_iso=item["timestamp_iso"],
            ) for item in raw_t["transitions"])
            task_snapshot = EvidenceTaskTrackerSnapshot(
                tasks=tuple(tracked_tasks), transitions=transitions,
                total_registered=raw_t["total_registered"], total_transitions=raw_t["total_transitions"],
                pending_count=raw_t["pending_count"], in_progress_count=raw_t["in_progress_count"],
                completed_count=raw_t["completed_count"], blocked_count=raw_t["blocked_count"],
                recovery_required_count=raw_t.get("recovery_required_count", 0),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvestigationStoreIntegrityError(f"invalid checkpoint snapshot payload: {exc}") from exc
        cls._validate_snapshots(hypothesis_snapshot, task_snapshot)
        return DiagnosticInvestigationCheckpoint(
            checkpoint_id=record.record_id, revision=record.revision,
            hypotheses=hypothesis_snapshot, tasks=task_snapshot,
            checksum=record.checksum, created_at_iso=record.created_at_iso,
        )

    @staticmethod
    def _validate_snapshots(hypotheses: HypothesisRegistrySnapshot, tasks: EvidenceTaskTrackerSnapshot) -> None:
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in
               (hypotheses.total_registered, hypotheses.total_assessments,
                tasks.total_registered, tasks.total_transitions)):
            raise InvestigationStoreIntegrityError("checkpoint counters must be non-negative integers")
        hypothesis_ids = {item.hypothesis_id for item in hypotheses.hypotheses}
        if len(hypothesis_ids) != len(hypotheses.hypotheses):
            raise InvestigationStoreIntegrityError("checkpoint contains duplicate hypothesis IDs")
        if len({item.task_id for item in tasks.tasks}) != len(tasks.tasks):
            raise InvestigationStoreIntegrityError("checkpoint contains duplicate task IDs")
        if any(item.hypothesis_id not in hypothesis_ids for item in tasks.tasks):
            raise InvestigationStoreIntegrityError("checkpoint task references an absent hypothesis")
        for item in tasks.tasks:
            if not isinstance(item.task, EvidenceCollectionTask):
                raise InvestigationStoreIntegrityError("checkpoint task definition has an invalid type")
            expected_task_id = f"{item.hypothesis_id}::{item.task.code}"
            if item.task_id != expected_task_id:
                raise InvestigationStoreIntegrityError(
                    "checkpoint task identity disagrees with its hypothesis and task definition"
                )
            if not isinstance(item.evidence_event_ids, tuple) or any(
                not isinstance(event_id, str) or not event_id.strip()
                for event_id in item.evidence_event_ids
            ) or len(set(item.evidence_event_ids)) != len(item.evidence_event_ids):
                raise InvestigationStoreIntegrityError("checkpoint task contains invalid evidence event references")
        if any(item.hypothesis_id not in hypothesis_ids for item in hypotheses.assessments):
            raise InvestigationStoreIntegrityError("checkpoint assessment references an absent hypothesis")
        state_counts = {
            state: sum(item.state == state for item in tasks.tasks)
            for state in ("pending", "in_progress", "completed", "blocked", "recovery_required")
        }
        if state_counts != {
            "pending": tasks.pending_count, "in_progress": tasks.in_progress_count,
            "completed": tasks.completed_count, "blocked": tasks.blocked_count,
            "recovery_required": tasks.recovery_required_count,
        }:
            raise InvestigationStoreIntegrityError("checkpoint task state counts do not match task records")
        if tasks.total_transitions != len(tasks.transitions):
            raise InvestigationStoreIntegrityError("checkpoint transition counter disagrees with retained transition count")
        if hypotheses.total_registered < len(hypotheses.hypotheses) or hypotheses.total_assessments < len(hypotheses.assessments):
            raise InvestigationStoreIntegrityError("checkpoint lifetime counters are below retained records")

        dispositions = {"under_review", "evidence_supports", "evidence_refutes", "insufficient_evidence"}
        hypothesis_by_id = {item.hypothesis_id: item for item in hypotheses.hypotheses}
        if any(item.disposition not in dispositions for item in hypotheses.hypotheses):
            raise InvestigationStoreIntegrityError("checkpoint contains an invalid hypothesis disposition")
        assessment_ids = [item.assessment_id for item in hypotheses.assessments]
        if any(isinstance(i, bool) or not isinstance(i, int) or i < 1 for i in assessment_ids) or len(set(assessment_ids)) != len(assessment_ids):
            raise InvestigationStoreIntegrityError("checkpoint contains invalid or duplicate assessment IDs")
        if assessment_ids != sorted(assessment_ids):
            raise InvestigationStoreIntegrityError("checkpoint assessment history is not ordered")
        latest_assessment = {}
        for item in hypotheses.assessments:
            if (item.disposition not in dispositions or not item.evidence_event_ids
                    or not isinstance(item.reviewer, str) or not item.reviewer.strip()
                    or not isinstance(item.rationale, str) or not item.rationale.strip()):
                raise InvestigationStoreIntegrityError("checkpoint contains an invalid assessment")
            latest_assessment[item.hypothesis_id] = item.disposition
        for hypothesis_id, disposition in latest_assessment.items():
            if hypothesis_by_id[hypothesis_id].disposition != disposition:
                raise InvestigationStoreIntegrityError("hypothesis disposition disagrees with its latest assessment")

        task_by_id = {item.task_id: item for item in tasks.tasks}
        allowed_transitions = {(None, "pending"), ("pending", "in_progress"),
                               ("pending", "blocked"), ("in_progress", "completed"),
                               ("in_progress", "pending"), ("in_progress", "blocked"),
                               ("in_progress", "recovery_required"), ("recovery_required", "pending"),
                               ("recovery_required", "blocked")}
        sequences = [item.sequence for item in tasks.transitions]
        if sequences != list(range(1, tasks.total_transitions + 1)):
            raise InvestigationStoreIntegrityError("checkpoint transition sequence has gaps or duplicates")
        current_state = {}
        start_counts = {}
        for transition in tasks.transitions:
            if transition.task_id not in task_by_id or (transition.from_state, transition.to_state) not in allowed_transitions:
                raise InvestigationStoreIntegrityError("checkpoint contains an invalid task transition")
            if (not isinstance(transition.actor, str) or not transition.actor.strip()
                    or not isinstance(transition.note, str) or not transition.note.strip()):
                raise InvestigationStoreIntegrityError("checkpoint transition is missing actor or note")
            if transition.task_id in current_state and transition.from_state != current_state[transition.task_id]:
                raise InvestigationStoreIntegrityError("checkpoint task transition chain is discontinuous")
            if transition.task_id not in current_state and transition.from_state is not None:
                raise InvestigationStoreIntegrityError("checkpoint task history lacks its initial transition")
            current_state[transition.task_id] = transition.to_state
            if transition.to_state == "in_progress":
                start_counts[transition.task_id] = start_counts.get(transition.task_id, 0) + 1
        for task_id, task in task_by_id.items():
            if task.state not in {"pending", "in_progress", "completed", "blocked", "recovery_required"}:
                raise InvestigationStoreIntegrityError("checkpoint contains an invalid task state")
            if (isinstance(task.attempts, bool) or not isinstance(task.attempts, int) or task.attempts < 0
                    or isinstance(task.max_attempts, bool) or not isinstance(task.max_attempts, int)
                    or task.max_attempts < 1 or task.attempts > task.max_attempts):
                raise InvestigationStoreIntegrityError("checkpoint contains invalid task attempt counts")
            if current_state.get(task_id) != task.state:
                raise InvestigationStoreIntegrityError("checkpoint task state disagrees with transition history")
            if start_counts.get(task_id, 0) != task.attempts:
                raise InvestigationStoreIntegrityError("checkpoint task attempts disagree with transition history")
