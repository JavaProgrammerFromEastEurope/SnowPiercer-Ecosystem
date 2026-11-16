from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .diagnostic_evidence_task_tracker import EvidenceTaskTrackerSnapshot, TrackedEvidenceTask

_OBSERVATION_STATUSES = frozenset({
    "confirmed_not_started", "confirmed_completed", "partial_or_unknown", "external_effect_detected",
})


@dataclass(frozen=True, slots=True)
class InterruptedTaskObservation:
    """Caller-supplied observation from an authoritative source; never fetched here."""

    task_id: str
    observation_status: str
    observed_at_iso: str
    observer: str
    note: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InterruptedTaskFinding:
    code: str
    severity: str
    task_id: str | None
    message: str


@dataclass(frozen=True, slots=True)
class InterruptedTaskAssessment:
    task_id: str
    observed_status: str | None
    recommendation: str
    finding_codes: tuple[str, ...]
    attempts: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class InterruptedTaskReconciliationReport:
    assessments: tuple[InterruptedTaskAssessment, ...]
    findings: tuple[InterruptedTaskFinding, ...]
    recovery_task_count: int
    assessed_task_count: int

    @property
    def has_blocking_findings(self) -> bool:
        return any(item.severity == "error" for item in self.findings)


class InterruptedTaskReconciler:
    """Read-only decision support for interrupted tasks; never changes or retries tasks.

    Observations are caller-supplied assertions. This component validates their shape and
    maps them to conservative recommendations; it cannot establish that an external
    system was actually inspected or that an asserted outcome is true.
    """

    @staticmethod
    def _aware_timestamp(value: str) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    def reconcile(
        self,
        snapshot: EvidenceTaskTrackerSnapshot,
        observations: Iterable[InterruptedTaskObservation],
    ) -> InterruptedTaskReconciliationReport:
        if not isinstance(snapshot, EvidenceTaskTrackerSnapshot):
            raise TypeError("snapshot must be an EvidenceTaskTrackerSnapshot")
        if isinstance(observations, (str, bytes)):
            raise TypeError("observations must be an iterable of InterruptedTaskObservation")
        try:
            supplied = tuple(observations)
        except TypeError as exc:
            raise TypeError("observations must be an iterable of InterruptedTaskObservation") from exc
        if any(not isinstance(item, InterruptedTaskObservation) for item in supplied):
            raise TypeError("every observation must be an InterruptedTaskObservation")

        tasks: dict[str, TrackedEvidenceTask] = {item.task_id: item for item in snapshot.tasks}
        if len(tasks) != len(snapshot.tasks):
            raise ValueError("task snapshot contains duplicate task IDs")
        recovery_tasks = {key: item for key, item in tasks.items() if item.state == "recovery_required"}
        by_task: dict[str, list[InterruptedTaskObservation]] = {}
        findings: list[InterruptedTaskFinding] = []

        def finding(code: str, severity: str, task_id: str | None, message: str) -> None:
            findings.append(InterruptedTaskFinding(code, severity, task_id, message))

        for item in supplied:
            if not isinstance(item.task_id, str) or not item.task_id.strip():
                finding("invalid_task_id", "error", None, "Observation task_id must be a non-empty string.")
                continue
            by_task.setdefault(item.task_id, []).append(item)
            if item.task_id not in tasks:
                finding("unknown_task", "error", item.task_id, "Observation refers to a task absent from the supplied snapshot.")
            elif item.task_id not in recovery_tasks:
                finding("task_not_recovery_required", "error", item.task_id, "Observation supplied for a task that is not recovery_required.")
            if not isinstance(item.observation_status, str) or item.observation_status not in _OBSERVATION_STATUSES:
                finding("invalid_observation_status", "error", item.task_id, "Observation status is not supported.")
            if not self._aware_timestamp(item.observed_at_iso):
                finding("invalid_observation_timestamp", "error", item.task_id, "Observation timestamp must be ISO-8601 with timezone.")
            if not isinstance(item.observer, str) or not item.observer.strip():
                finding("missing_observer", "error", item.task_id, "Observation must identify its observer.")
            if not isinstance(item.note, str) or not item.note.strip():
                finding("missing_observation_note", "error", item.task_id, "Observation must include a substantive note.")
            if not isinstance(item.evidence_ids, tuple) or any(not isinstance(value, str) or not value.strip() for value in item.evidence_ids):
                finding("invalid_evidence_ids", "error", item.task_id, "evidence_ids must be a tuple of non-empty strings.")
            elif len(set(item.evidence_ids)) != len(item.evidence_ids):
                finding("duplicate_evidence_ids", "error", item.task_id, "Observation evidence IDs must be unique.")

        assessments: list[InterruptedTaskAssessment] = []
        for task_id, task in sorted(recovery_tasks.items()):
            matching = by_task.get(task_id, [])
            codes: list[str] = []
            if not matching:
                recommendation = "keep_recovery_required"
                codes.append("observation_missing")
                finding("observation_missing", "warning", task_id, "No external outcome observation supplied; retry is not safe to authorize.")
                status = None
            elif len(matching) > 1:
                recommendation = "keep_recovery_required"
                codes.append("duplicate_observations")
                finding("duplicate_observations", "error", task_id, "Multiple observations exist for one task; resolve their conflict before a decision.")
                status = None
            else:
                observation = matching[0]
                status = observation.observation_status if isinstance(observation.observation_status, str) and observation.observation_status in _OBSERVATION_STATUSES else None
                # Any validation error for this task prevents a recommendation to retry.
                invalid = any(item.task_id == task_id and item.severity == "error" for item in findings)
                if invalid or status is None:
                    recommendation = "keep_recovery_required"
                    codes.append("observation_invalid")
                elif status == "confirmed_not_started":
                    if task.attempts < task.max_attempts:
                        recommendation = "safe_to_retry_after_authorized_review"
                    else:
                        recommendation = "require_block_or_manual_review"
                        codes.append("retry_limit_exhausted")
                        finding("retry_limit_exhausted", "warning", task_id, "The attempt limit is exhausted; do not return this task to pending.")
                elif status == "confirmed_completed":
                    recommendation = "completed_outcome_requires_independent_verification"
                    codes.append("completion_not_applied_automatically")
                    finding("completion_not_applied_automatically", "warning", task_id, "A completion claim must be checked against result and evidence records before state changes.")
                elif status == "external_effect_detected":
                    recommendation = "keep_recovery_required_and_reconcile_external_effects"
                    codes.append("external_effect_requires_reconciliation")
                    finding("external_effect_requires_reconciliation", "warning", task_id, "An external side effect may already exist; reconcile it before any retry.")
                else:
                    recommendation = "keep_recovery_required"
                    codes.append("outcome_ambiguous")
                    finding("outcome_ambiguous", "warning", task_id, "Outcome is partial or unknown; do not retry until external state is resolved.")
            assessments.append(InterruptedTaskAssessment(
                task_id=task_id, observed_status=status, recommendation=recommendation,
                finding_codes=tuple(sorted(set(codes))), attempts=task.attempts, max_attempts=task.max_attempts,
            ))

        findings.sort(key=lambda item: (item.severity, item.task_id or "", item.code, item.message))
        return InterruptedTaskReconciliationReport(
            assessments=tuple(assessments), findings=tuple(findings),
            recovery_task_count=len(recovery_tasks),
            assessed_task_count=sum(item.observed_status is not None for item in assessments),
        )
