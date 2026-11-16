from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .command_event import CommandEvent
from .event_type import CommandEventType
from .event_registry import EventRegistry
from .diagnostic_hypothesis_registry import HypothesisRegistrySnapshot


@dataclass(frozen=True, slots=True)
class DiagnosticEvidenceIssue:
    """One deterministic evidence-quality finding; it does not judge root cause."""

    code: str
    severity: str
    hypothesis_id: str
    assessment_id: int | None
    event_id: str | None
    message: str


@dataclass(frozen=True, slots=True)
class DiagnosticEvidenceValidation:
    """Read-only validation result over retained hypotheses and supplied events."""

    hypotheses_checked: int
    assessments_checked: int
    events_supplied: int
    issues: tuple[DiagnosticEvidenceIssue, ...]
    history_complete: bool

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    @property
    def is_consistent(self) -> bool:
        return self.error_count == 0


class DiagnosticEvidenceValidator:
    """Validate reference integrity and chronology without inferring causation.

    The caller supplies the event inventory available to the review. If that inventory
    is only a bounded timeline snapshot, set ``history_complete=False`` (the default)
    so the result explicitly warns that missing references may have been evicted.
    """

    @staticmethod
    def _parse_aware(value: str) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed

    def validate_from_registry(
        self, snapshot: HypothesisRegistrySnapshot, registry: EventRegistry,
    ) -> DiagnosticEvidenceValidation:
        """Validate against the registry's retained event snapshot.

        EventRegistry is bounded and in-memory, so this method deliberately marks
        history as incomplete. Missing references remain warnings, not proof that an
        event never existed. Use ``validate(..., history_complete=True)`` only when
        the caller can establish completeness from an authoritative source.
        """
        if not isinstance(registry, EventRegistry):
            raise TypeError("registry must be an EventRegistry")
        return self.validate(snapshot, registry.all_events(), history_complete=False)

    def validate(
        self,
        snapshot: HypothesisRegistrySnapshot,
        events: Iterable[CommandEvent],
        *,
        history_complete: bool = False,
    ) -> DiagnosticEvidenceValidation:
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

        issues: list[DiagnosticEvidenceIssue] = []
        by_id: dict[str, CommandEvent] = {}
        duplicate_ids: set[str] = set()
        for event in event_items:
            if event.event_id in by_id:
                duplicate_ids.add(event.event_id)
            else:
                by_id[event.event_id] = event
        for event_id in sorted(duplicate_ids):
            issues.append(DiagnosticEvidenceIssue(
                "duplicate_event_id", "error", "", None, event_id,
                "Supplied event inventory contains duplicate event IDs; references are ambiguous.",
            ))

        hypotheses = {hypothesis.hypothesis_id: hypothesis for hypothesis in snapshot.hypotheses}
        assessments_by_hypothesis: dict[str, list] = {key: [] for key in hypotheses}
        for assessment in snapshot.assessments:
            assessments_by_hypothesis.setdefault(assessment.hypothesis_id, []).append(assessment)
            if assessment.hypothesis_id not in hypotheses:
                issues.append(DiagnosticEvidenceIssue(
                    "orphan_assessment", "error", assessment.hypothesis_id, assessment.assessment_id, None,
                    "Assessment refers to a hypothesis that is not present in the supplied snapshot.",
                ))

        for hypothesis in snapshot.hypotheses:
            diagnostic = by_id.get(hypothesis.diagnostic_event_id)
            if diagnostic is None:
                issues.append(DiagnosticEvidenceIssue(
                    "missing_diagnostic_event", "warning" if not history_complete else "error",
                    hypothesis.hypothesis_id, None, hypothesis.diagnostic_event_id,
                    "The originating diagnostic event is absent from the supplied event inventory.",
                ))
            else:
                if diagnostic.command_id != hypothesis.command_id:
                    issues.append(DiagnosticEvidenceIssue(
                        "diagnostic_command_mismatch", "error", hypothesis.hypothesis_id, None,
                        hypothesis.diagnostic_event_id,
                        "The originating diagnostic event command ID differs from the hypothesis command ID.",
                    ))
                if diagnostic.event_type is not CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC:
                    issues.append(DiagnosticEvidenceIssue(
                        "diagnostic_event_type_mismatch", "error", hypothesis.hypothesis_id, None,
                        hypothesis.diagnostic_event_id,
                        "The originating event is not an execution-integrity diagnostic event.",
                    ))
                diagnostic_code = diagnostic.payload.get("code")
                if diagnostic_code != hypothesis.diagnostic_code:
                    issues.append(DiagnosticEvidenceIssue(
                        "diagnostic_code_mismatch", "error", hypothesis.hypothesis_id, None,
                        hypothesis.diagnostic_event_id,
                        "The diagnostic event code differs from the registered hypothesis code.",
                    ))

            for assessment in assessments_by_hypothesis.get(hypothesis.hypothesis_id, ()):
                assessed_at = self._parse_aware(assessment.assessed_at_iso)
                if assessed_at is None:
                    issues.append(DiagnosticEvidenceIssue(
                        "invalid_assessment_timestamp", "error", hypothesis.hypothesis_id,
                        assessment.assessment_id, None,
                        "Assessment timestamp is invalid or lacks timezone information.",
                    ))
                if len(set(assessment.evidence_event_ids)) != len(assessment.evidence_event_ids):
                    issues.append(DiagnosticEvidenceIssue(
                        "duplicate_evidence_reference", "error", hypothesis.hypothesis_id,
                        assessment.assessment_id, None,
                        "Assessment cites the same event ID more than once.",
                    ))
                for event_id in assessment.evidence_event_ids:
                    evidence_event = by_id.get(event_id)
                    if evidence_event is None:
                        issues.append(DiagnosticEvidenceIssue(
                            "missing_evidence_event", "warning" if not history_complete else "error",
                            hypothesis.hypothesis_id, assessment.assessment_id, event_id,
                            "Cited evidence event is absent from the supplied event inventory.",
                        ))
                        continue
                    if evidence_event.command_id != hypothesis.command_id:
                        issues.append(DiagnosticEvidenceIssue(
                            "cross_command_evidence", "warning", hypothesis.hypothesis_id,
                            assessment.assessment_id, event_id,
                            "Evidence belongs to a different command; confirm that cross-command use is intentional.",
                        ))
                    if assessed_at is not None and evidence_event.timestamp > assessed_at:
                        issues.append(DiagnosticEvidenceIssue(
                            "evidence_after_assessment", "error", hypothesis.hypothesis_id,
                            assessment.assessment_id, event_id,
                            "Evidence event timestamp is later than the assessment timestamp.",
                        ))

        if not history_complete:
            issues.append(DiagnosticEvidenceIssue(
                "history_may_be_incomplete", "warning", "", None, None,
                "Validation uses a caller-supplied event inventory that may be bounded or incomplete; "
                "missing references cannot be treated as proof that an event never existed.",
            ))

        issues.sort(key=lambda item: (
            item.severity, item.code, item.hypothesis_id, item.assessment_id or 0, item.event_id or ""
        ))
        return DiagnosticEvidenceValidation(
            hypotheses_checked=len(snapshot.hypotheses),
            assessments_checked=len(snapshot.assessments),
            events_supplied=len(event_items),
            issues=tuple(issues),
            history_complete=history_complete,
        )
