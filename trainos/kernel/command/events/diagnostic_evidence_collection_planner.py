from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .command_event import CommandEvent
from .diagnostic_evidence_readiness import DiagnosticEvidenceReadinessAssessor, EvidenceReadinessReport
from .diagnostic_evidence_validator import DiagnosticEvidenceValidation, DiagnosticEvidenceValidator
from .diagnostic_hypothesis_registry import HypothesisRegistrySnapshot


@dataclass(frozen=True, slots=True)
class EvidenceCollectionTask:
    """One actionable data-collection or integrity task; never an equipment command."""

    code: str
    priority: str
    description: str
    required_for_review: bool


@dataclass(frozen=True, slots=True)
class HypothesisEvidencePlan:
    """Evidence acquisition plan for one hypothesis, without a causal verdict."""

    hypothesis_id: str
    readiness_status: str
    tasks: tuple[EvidenceCollectionTask, ...]


@dataclass(frozen=True, slots=True)
class EvidenceCollectionPlan:
    """Read-only plan derived from current retained events and registry state."""

    hypotheses_planned: int
    task_count: int
    high_priority_task_count: int
    plans: tuple[HypothesisEvidencePlan, ...]
    history_complete: bool
    limitations: tuple[str, ...]


class DiagnosticEvidenceCollectionPlanner:
    """Turn evidence-quality gaps into explicit, auditable follow-up tasks.

    Tasks describe information to retrieve or review. They do not trigger data access,
    alter a hypothesis, execute a command, or establish root cause.
    """

    _ISSUE_TASKS: dict[str, tuple[str, str]] = {
        "missing_diagnostic_event": ("recover_diagnostic_event", "Recover the originating diagnostic event from an authoritative history."),
        "missing_evidence_event": ("recover_evidence_event", "Retrieve the referenced evidence event from an authoritative source."),
        "history_may_be_incomplete": ("complete_event_history", "Obtain a complete, authoritative event history and rerun validation."),
        "cross_command_evidence": ("review_cross_command_evidence", "Verify why evidence from another command is relevant and document the linkage."),
        "duplicate_event_id": ("resolve_duplicate_event_ids", "Resolve duplicate event identifiers against the authoritative event source."),
        "orphan_assessment": ("resolve_orphan_assessment", "Resolve assessments that refer to a missing or evicted hypothesis."),
        "diagnostic_command_mismatch": ("verify_diagnostic_command", "Verify the diagnostic event and hypothesis command identifiers."),
        "diagnostic_event_type_mismatch": ("verify_diagnostic_type", "Confirm the referenced event is a diagnostic event of the expected type."),
        "diagnostic_code_mismatch": ("verify_diagnostic_code", "Reconcile the diagnostic code with the originating event payload."),
        "invalid_assessment_timestamp": ("verify_assessment_timestamp", "Recover or correct the assessment timestamp from an authoritative record."),
        "duplicate_evidence_reference": ("deduplicate_evidence_references", "Resolve duplicate references while preserving the original assessment history."),
        "evidence_after_assessment": ("resolve_evidence_chronology", "Verify event and assessment timestamps, including timezone and clock-source quality."),
    }

    def __init__(
        self,
        validator: DiagnosticEvidenceValidator | None = None,
        assessor: DiagnosticEvidenceReadinessAssessor | None = None,
    ) -> None:
        if validator is not None and not isinstance(validator, DiagnosticEvidenceValidator):
            raise TypeError("validator must be a DiagnosticEvidenceValidator or None")
        if assessor is not None and not isinstance(assessor, DiagnosticEvidenceReadinessAssessor):
            raise TypeError("assessor must be a DiagnosticEvidenceReadinessAssessor or None")
        self._validator = validator or DiagnosticEvidenceValidator()
        self._assessor = assessor or DiagnosticEvidenceReadinessAssessor(self._validator)

    def plan(
        self,
        snapshot: HypothesisRegistrySnapshot,
        events: Iterable[CommandEvent],
        *,
        history_complete: bool = False,
    ) -> EvidenceCollectionPlan:
        if not isinstance(snapshot, HypothesisRegistrySnapshot):
            raise TypeError("snapshot must be a HypothesisRegistrySnapshot")
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

        validation: DiagnosticEvidenceValidation = self._validator.validate(
            snapshot, event_items, history_complete=history_complete
        )
        readiness: EvidenceReadinessReport = self._assessor.assess(
            snapshot, event_items, history_complete=history_complete
        )
        hypothesis_by_id = {item.hypothesis_id: item for item in snapshot.hypotheses}
        issue_by_hypothesis: dict[str, set[str]] = {}
        global_issue_codes: set[str] = set()
        for issue in validation.issues:
            if issue.hypothesis_id:
                issue_by_hypothesis.setdefault(issue.hypothesis_id, set()).add(issue.code)
            else:
                global_issue_codes.add(issue.code)

        plans: list[HypothesisEvidencePlan] = []
        for result in readiness.results:
            tasks: dict[str, EvidenceCollectionTask] = {}
            codes = issue_by_hypothesis.get(result.hypothesis_id, set()) | global_issue_codes
            for code in sorted(codes):
                mapping = self._ISSUE_TASKS.get(code)
                if mapping is None:
                    continue
                task_code, description = mapping
                priority = "high" if code in {
                    "duplicate_event_id", "diagnostic_command_mismatch", "diagnostic_event_type_mismatch",
                    "diagnostic_code_mismatch", "invalid_assessment_timestamp",
                    "duplicate_evidence_reference", "evidence_after_assessment",
                } else "normal"
                tasks[task_code] = EvidenceCollectionTask(
                    code=task_code, priority=priority, description=description,
                    required_for_review=True,
                )

            hypothesis = hypothesis_by_id[result.hypothesis_id]
            if result.evidence_event_count < 2:
                tasks.setdefault("collect_additional_events", EvidenceCollectionTask(
                    "collect_additional_events", "normal",
                    "Collect at least two distinct, relevant evidence events; do not treat copies of one event as independent evidence.", True,
                ))
            if len(result.distinct_evidence_types) < 2:
                tasks.setdefault("seek_source_diversity", EvidenceCollectionTask(
                    "seek_source_diversity", "normal",
                    "Seek a second relevant event type or independent source and document whether it is genuinely independent.", True,
                ))
            if result.assessments_count == 0:
                tasks.setdefault("request_explicit_assessment", EvidenceCollectionTask(
                    "request_explicit_assessment", "normal",
                    "Request an explicit, traceable assessment from an authorized reviewer.", True,
                ))
            elif hypothesis.disposition in {"under_review", "insufficient_evidence"}:
                tasks.setdefault("resolve_open_assessment", EvidenceCollectionTask(
                    "resolve_open_assessment", "normal",
                    "Address the stated evidence gaps and obtain a new explicit assessment; do not auto-change the disposition.", True,
                ))
            if hypothesis.disposition in {"evidence_supports", "evidence_refutes"}:
                tasks.setdefault("independent_expert_review", EvidenceCollectionTask(
                    "independent_expert_review", "normal",
                    "Have an authorized reviewer examine both supporting and contradictory evidence before drawing conclusions.", True,
                ))

            ordered_tasks = tuple(sorted(tasks.values(), key=lambda task: (task.priority != "high", task.code)))
            plans.append(HypothesisEvidencePlan(result.hypothesis_id, result.status, ordered_tasks))

        plans.sort(key=lambda item: item.hypothesis_id)
        task_count = sum(len(item.tasks) for item in plans)
        high_count = sum(task.priority == "high" for item in plans for task in item.tasks)
        limitations = []
        if not history_complete:
            limitations.append("Event history may be incomplete; missing references do not prove an event never existed.")
        limitations.append("Tasks are recommendations only; this planner does not retrieve data or execute actions.")
        limitations.append("Event/type diversity is not proof of independent evidence or causal linkage.")
        return EvidenceCollectionPlan(
            hypotheses_planned=len(plans), task_count=task_count,
            high_priority_task_count=high_count, plans=tuple(plans),
            history_complete=history_complete, limitations=tuple(limitations),
        )
