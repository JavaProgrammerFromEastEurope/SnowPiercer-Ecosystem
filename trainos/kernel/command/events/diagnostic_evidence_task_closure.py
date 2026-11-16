from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .command_event import CommandEvent
from .diagnostic_evidence_task_tracker import EvidenceTaskTrackerSnapshot, TrackedEvidenceTask
from .diagnostic_evidence_validator import DiagnosticEvidenceIssue, DiagnosticEvidenceValidation, DiagnosticEvidenceValidator
from .diagnostic_hypothesis_registry import HypothesisRegistrySnapshot


@dataclass(frozen=True, slots=True)
class EvidenceTaskClosureFinding:
    """A traceable issue found while checking a claimed task completion."""

    task_id: str
    hypothesis_id: str
    code: str
    severity: str
    message: str
    event_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceTaskClosureResult:
    """Verification outcome for one evidence task; not a causal verdict."""

    task_id: str
    hypothesis_id: str
    state: str
    status: str
    findings: tuple[EvidenceTaskClosureFinding, ...]
    verified_evidence_event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceTaskClosureReport:
    """Read-only closure verification across task, hypothesis, and event snapshots."""

    results: tuple[EvidenceTaskClosureResult, ...]
    hypothesis_validation: DiagnosticEvidenceValidation
    history_complete: bool
    verified_count: int
    needs_review_count: int
    blocked_count: int
    open_task_count: int
    recovery_required_count: int = 0

    @property
    def all_closed_and_verified(self) -> bool:
        return (self.open_task_count == 0 and self.needs_review_count == 0
                and self.blocked_count == 0 and self.recovery_required_count == 0)


class DiagnosticEvidenceTaskClosureVerifier:
    """Check that completed evidence tasks have traceable, temporally valid outputs.

    Verification is read-only. It does not change task state, amend hypotheses, fetch
    evidence, or execute commands. A verified task means its supplied references pass
    these checks, not that the evidence proves a root cause.
    """

    def __init__(self, validator: DiagnosticEvidenceValidator | None = None) -> None:
        if validator is not None and not isinstance(validator, DiagnosticEvidenceValidator):
            raise TypeError("validator must be a DiagnosticEvidenceValidator or None")
        self._validator = validator or DiagnosticEvidenceValidator()

    @staticmethod
    def _parse_aware(value: str) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if result.tzinfo is None or result.utcoffset() is None:
            return None
        return result

    def verify(
        self,
        task_snapshot: EvidenceTaskTrackerSnapshot,
        hypothesis_snapshot: HypothesisRegistrySnapshot,
        events: Iterable[CommandEvent],
        *,
        history_complete: bool = False,
    ) -> EvidenceTaskClosureReport:
        if not isinstance(task_snapshot, EvidenceTaskTrackerSnapshot):
            raise TypeError("task_snapshot must be an EvidenceTaskTrackerSnapshot")
        if not isinstance(hypothesis_snapshot, HypothesisRegistrySnapshot):
            raise TypeError("hypothesis_snapshot must be a HypothesisRegistrySnapshot")
        if isinstance(events, (str, bytes)):
            raise TypeError("events must be an iterable of CommandEvent")
        try:
            event_items = tuple(events)
        except TypeError as exc:
            raise TypeError("events must be an iterable of CommandEvent") from exc
        if any(not isinstance(event, CommandEvent) for event in event_items):
            raise TypeError("every event must be a CommandEvent")
        if not isinstance(history_complete, bool):
            raise TypeError("history_complete must be a bool")

        hypothesis_by_id = {item.hypothesis_id: item for item in hypothesis_snapshot.hypotheses}
        event_by_id: dict[str, CommandEvent] = {}
        duplicate_event_ids: set[str] = set()
        for event in event_items:
            if event.event_id in event_by_id:
                duplicate_event_ids.add(event.event_id)
            else:
                event_by_id[event.event_id] = event
        validation = self._validator.validate(
            hypothesis_snapshot, event_items, history_complete=history_complete
        )
        validation_by_hypothesis: dict[str, list[DiagnosticEvidenceIssue]] = {}
        global_issues: list[DiagnosticEvidenceIssue] = []
        for issue in validation.issues:
            if issue.hypothesis_id:
                validation_by_hypothesis.setdefault(issue.hypothesis_id, []).append(issue)
            else:
                global_issues.append(issue)

        results: list[EvidenceTaskClosureResult] = []
        for task in sorted(task_snapshot.tasks, key=lambda item: item.task_id):
            findings: list[EvidenceTaskClosureFinding] = []
            verified_ids: list[str] = []
            if task.state != "completed":
                findings: tuple[EvidenceTaskClosureFinding, ...] = ()
                if task.state == "recovery_required":
                    findings = (EvidenceTaskClosureFinding(
                        task.task_id, task.hypothesis_id, "interrupted_task_recovery_unresolved", "error",
                        "Task outcome is unresolved after interruption; closure is blocked until the external outcome is reconciled and an explicit decision is recorded.",
                    ),)
                results.append(EvidenceTaskClosureResult(
                    task_id=task.task_id, hypothesis_id=task.hypothesis_id,
                    state=task.state, status="open", findings=findings, verified_evidence_event_ids=(),
                ))
                continue

            def add(code: str, severity: str, message: str, event_id: str | None = None) -> None:
                findings.append(EvidenceTaskClosureFinding(
                    task.task_id, task.hypothesis_id, code, severity, message, event_id
                ))

            hypothesis = hypothesis_by_id.get(task.hypothesis_id)
            if hypothesis is None:
                add("missing_hypothesis", "error", "The task refers to a hypothesis absent from the supplied registry snapshot.")
            if not isinstance(task.result_note, str) or not task.result_note.strip():
                add("missing_result_note", "error", "Completed task has no substantive result note.")
            if task.task.required_for_review and not task.evidence_event_ids:
                add("missing_task_evidence", "error", "Task is required for review but completion cites no evidence events.")
            completed_at = self._parse_aware(task.updated_at_iso)
            if completed_at is None:
                add("invalid_completion_timestamp", "error", "Task completion timestamp is invalid or lacks timezone information.")

            for event_id in task.evidence_event_ids:
                if event_id in duplicate_event_ids:
                    add("ambiguous_evidence_event_id", "error", "Evidence event ID is duplicated in the supplied inventory.", event_id)
                    continue
                event = event_by_id.get(event_id)
                if event is None:
                    severity = "error" if history_complete else "warning"
                    add("missing_task_evidence_event", severity,
                        "Task evidence event is absent from the supplied inventory; the event may be outside retained history.", event_id)
                    continue
                if hypothesis is not None and event.command_id != hypothesis.command_id:
                    add("cross_command_task_evidence", "warning",
                        "Task evidence belongs to a different command than its hypothesis; explicit linkage review is needed.", event_id)
                if completed_at is not None and event.timestamp > completed_at:
                    add("evidence_after_task_completion", "error",
                        "Evidence event occurred after the task was recorded as completed.", event_id)
                else:
                    verified_ids.append(event_id)

            for issue in validation_by_hypothesis.get(task.hypothesis_id, ()):
                findings.append(EvidenceTaskClosureFinding(
                    task.task_id, task.hypothesis_id, f"hypothesis_{issue.code}", issue.severity,
                    issue.message, issue.event_id,
                ))
            for issue in global_issues:
                findings.append(EvidenceTaskClosureFinding(
                    task.task_id, task.hypothesis_id, f"inventory_{issue.code}", issue.severity,
                    issue.message, issue.event_id,
                ))
            if not history_complete:
                # The validator emits this globally; retain an explicit limitation even if
                # a custom validator changes its global diagnostics in a future version.
                if not any(item.code == "inventory_history_may_be_incomplete" for item in findings):
                    add("history_may_be_incomplete", "warning",
                        "The supplied event inventory is not declared complete; closure cannot be fully certified.")

            findings.sort(key=lambda item: (item.severity, item.code, item.event_id or "", item.message))
            if any(item.severity == "error" for item in findings):
                status = "blocked"
            elif findings or not history_complete:
                status = "needs_review"
            else:
                status = "verified"
            results.append(EvidenceTaskClosureResult(
                task_id=task.task_id, hypothesis_id=task.hypothesis_id,
                state=task.state, status=status, findings=tuple(findings),
                verified_evidence_event_ids=tuple(verified_ids),
            ))

        verified_count = sum(item.status == "verified" for item in results)
        needs_review_count = sum(item.status == "needs_review" for item in results)
        blocked_count = sum(item.status == "blocked" for item in results)
        open_count = sum(item.status == "open" for item in results)
        recovery_required_count = sum(item.state == "recovery_required" for item in results)
        return EvidenceTaskClosureReport(
            results=tuple(results), hypothesis_validation=validation,
            history_complete=history_complete, verified_count=verified_count,
            needs_review_count=needs_review_count, blocked_count=blocked_count,
            open_task_count=open_count, recovery_required_count=recovery_required_count,
        )
