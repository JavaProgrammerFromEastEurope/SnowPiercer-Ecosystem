from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .command_event import CommandEvent
from .diagnostic_evidence_validator import DiagnosticEvidenceValidator
from .diagnostic_hypothesis_registry import HypothesisRegistrySnapshot
from .event_type import CommandEventType


@dataclass(frozen=True, slots=True)
class HypothesisReadiness:
    """Evidence-quality summary for expert review, not a root-cause verdict."""

    hypothesis_id: str
    status: str
    evidence_event_count: int
    distinct_evidence_types: tuple[str, ...]
    assessments_count: int
    issue_codes: tuple[str, ...]
    recommendations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceReadinessReport:
    """Read-only readiness report for a supplied registry and event inventory."""

    hypotheses_checked: int
    ready_for_expert_review: int
    needs_more_evidence: int
    blocked_by_integrity_issues: int
    results: tuple[HypothesisReadiness, ...]
    history_complete: bool


class DiagnosticEvidenceReadinessAssessor:
    """Assess evidence readiness conservatively without inferring causation.

    Distinct event IDs/types are only a basic completeness signal. The assessor cannot
    establish statistical independence, authenticity, sensor quality, or causal linkage.
    """

    _BLOCKING_ISSUES = frozenset({
        "duplicate_event_id", "orphan_assessment", "diagnostic_command_mismatch",
        "diagnostic_event_type_mismatch", "diagnostic_code_mismatch",
        "invalid_assessment_timestamp", "duplicate_evidence_reference",
        "evidence_after_assessment",
    })

    def __init__(self, validator: DiagnosticEvidenceValidator | None = None) -> None:
        if validator is not None and not isinstance(validator, DiagnosticEvidenceValidator):
            raise TypeError("validator must be a DiagnosticEvidenceValidator or None")
        self._validator = validator or DiagnosticEvidenceValidator()

    def assess(
        self,
        snapshot: HypothesisRegistrySnapshot,
        events: Iterable[CommandEvent],
        *,
        history_complete: bool = False,
    ) -> EvidenceReadinessReport:
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

        validation = self._validator.validate(snapshot, event_items, history_complete=history_complete)
        by_id: dict[str, CommandEvent] = {}
        duplicate_ids: set[str] = set()
        for event in event_items:
            if event.event_id in by_id:
                duplicate_ids.add(event.event_id)
            else:
                by_id[event.event_id] = event

        assessments_by_hypothesis: dict[str, list] = {}
        for assessment in snapshot.assessments:
            assessments_by_hypothesis.setdefault(assessment.hypothesis_id, []).append(assessment)

        results: list[HypothesisReadiness] = []
        for hypothesis in snapshot.hypotheses:
            assessments = assessments_by_hypothesis.get(hypothesis.hypothesis_id, [])
            latest = max(assessments, key=lambda item: item.assessment_id) if assessments else None
            evidence_ids = tuple(dict.fromkeys(latest.evidence_event_ids)) if latest else ()
            present_events = [by_id[event_id] for event_id in evidence_ids
                              if event_id in by_id and event_id not in duplicate_ids]
            evidence_types = tuple(sorted({event.event_type.value for event in present_events}))
            relevant_issues = [issue for issue in validation.issues
                               if issue.hypothesis_id == hypothesis.hypothesis_id]
            issue_codes = tuple(sorted({issue.code for issue in relevant_issues}))
            blocking = any(issue.severity == "error" for issue in relevant_issues)
            recommendations: list[str] = []

            if hypothesis.diagnostic_event_id not in by_id:
                recommendations.append("Recover the originating diagnostic event from an authoritative history.")
            if not history_complete:
                recommendations.append("Re-run validation against a complete, authoritative event history.")
            if latest is None:
                recommendations.append("Record an explicit assessment with traceable evidence references.")
            if len(present_events) < 2:
                recommendations.append("Collect at least two distinct, relevant evidence events before expert review.")
            if len(evidence_types) < 2:
                recommendations.append("Seek evidence from a second event type; event-type diversity does not prove independence.")
            if latest is not None and latest.disposition in {"under_review", "insufficient_evidence"}:
                recommendations.append("Resolve the open evidence gap before treating the assessment as review-ready.")
            if blocking:
                recommendations.append("Resolve blocking evidence-integrity errors before relying on this hypothesis.")
            if latest is not None and latest.disposition in {"evidence_supports", "evidence_refutes"}:
                recommendations.append("Have an authorized reviewer independently examine the evidence and rationale.")

            if blocking:
                status = "blocked_by_integrity_issues"
            elif (not history_complete or latest is None or len(present_events) < 2
                  or len(evidence_types) < 2
                  or latest.disposition in {"under_review", "insufficient_evidence"}
                  or any(issue.severity == "warning" for issue in relevant_issues)):
                status = "needs_more_evidence"
            else:
                status = "ready_for_expert_review"

            results.append(HypothesisReadiness(
                hypothesis_id=hypothesis.hypothesis_id,
                status=status,
                evidence_event_count=len(present_events),
                distinct_evidence_types=evidence_types,
                assessments_count=len(assessments),
                issue_codes=issue_codes,
                recommendations=tuple(dict.fromkeys(recommendations)),
            ))

        results.sort(key=lambda result: (result.status, result.hypothesis_id))
        return EvidenceReadinessReport(
            hypotheses_checked=len(results),
            ready_for_expert_review=sum(item.status == "ready_for_expert_review" for item in results),
            needs_more_evidence=sum(item.status == "needs_more_evidence" for item in results),
            blocked_by_integrity_issues=sum(item.status == "blocked_by_integrity_issues" for item in results),
            results=tuple(results),
            history_complete=history_complete,
        )
