from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import RLock
from typing import Iterable

from .execution_event_sequence_analyzer import SequencePatternFinding


_DISPOSITIONS = frozenset({
    "under_review",
    "evidence_supports",
    "evidence_refutes",
    "insufficient_evidence",
})


@dataclass(frozen=True, slots=True)
class DiagnosticHypothesis:
    """A reviewable hypothesis derived from observed events, not a proven cause."""

    hypothesis_id: str
    diagnostic_event_id: str
    command_id: str
    diagnostic_code: str
    pattern_code: str
    observed_event_types: tuple[str, ...]
    evidence_note: str
    analyzer_confidence: str
    disposition: str = "under_review"


@dataclass(frozen=True, slots=True)
class HypothesisAssessment:
    """An explicit human/system review decision with traceable evidence references."""

    assessment_id: int
    hypothesis_id: str
    disposition: str
    evidence_event_ids: tuple[str, ...]
    reviewer: str
    rationale: str
    assessed_at_iso: str


@dataclass(frozen=True, slots=True)
class HypothesisRegistrySnapshot:
    """Consistent immutable view of currently retained hypotheses and review history."""

    hypotheses: tuple[DiagnosticHypothesis, ...]
    assessments: tuple[HypothesisAssessment, ...]
    total_registered: int
    total_assessments: int


class DiagnosticHypothesisRegistry:
    """Bounded in-memory review registry; never infers a disposition automatically.

    A repeated registration of the same diagnostic-event/pattern pair is idempotent.
    Assessments are append-only while retained. When the hypothesis limit is reached,
    the oldest hypothesis and its retained assessment history are evicted together.
    This is not a durable audit store.
    """

    def __init__(self, max_hypotheses: int = 1000) -> None:
        if isinstance(max_hypotheses, bool) or not isinstance(max_hypotheses, int) or max_hypotheses < 1:
            raise ValueError("max_hypotheses must be a positive integer")
        self._max_hypotheses = max_hypotheses
        self._lock = RLock()
        self._hypotheses: dict[str, DiagnosticHypothesis] = {}
        self._assessments: list[HypothesisAssessment] = []
        self._next_assessment_id = 1
        self._total_registered = 0
        self._total_assessments = 0

    @staticmethod
    def _hypothesis_id(finding: SequencePatternFinding) -> str:
        return f"{finding.diagnostic_event_id}::{finding.pattern_code}"

    def register_findings(
        self, findings: Iterable[SequencePatternFinding]
    ) -> tuple[DiagnosticHypothesis, ...]:
        """Register observed pattern findings as hypotheses in `under_review` state."""
        if isinstance(findings, (str, bytes)):
            raise TypeError("findings must be an iterable of SequencePatternFinding")
        try:
            items = tuple(findings)
        except TypeError as exc:
            raise TypeError("findings must be an iterable of SequencePatternFinding") from exc
        if any(not isinstance(item, SequencePatternFinding) for item in items):
            raise TypeError("every finding must be a SequencePatternFinding")

        registered: list[DiagnosticHypothesis] = []
        with self._lock:
            for finding in items:
                hypothesis_id = self._hypothesis_id(finding)
                existing = self._hypotheses.get(hypothesis_id)
                candidate = DiagnosticHypothesis(
                    hypothesis_id=hypothesis_id,
                    diagnostic_event_id=finding.diagnostic_event_id,
                    command_id=finding.command_id,
                    diagnostic_code=finding.diagnostic_code,
                    pattern_code=finding.pattern_code,
                    observed_event_types=tuple(finding.observed_event_types),
                    evidence_note=finding.evidence_note,
                    analyzer_confidence=finding.confidence,
                )
                if existing is not None:
                    if replace(existing, disposition="under_review") != candidate:
                        raise ValueError(f"conflicting finding for hypothesis {hypothesis_id}")
                    registered.append(existing)
                    continue
                self._hypotheses[hypothesis_id] = candidate
                self._total_registered += 1
                registered.append(candidate)
                while len(self._hypotheses) > self._max_hypotheses:
                    oldest_id = next(iter(self._hypotheses))
                    del self._hypotheses[oldest_id]
                    self._assessments = [a for a in self._assessments if a.hypothesis_id != oldest_id]
        return tuple(registered)

    def assess(
        self,
        hypothesis_id: str,
        disposition: str,
        evidence_event_ids: Iterable[str],
        reviewer: str,
        rationale: str,
    ) -> HypothesisAssessment:
        """Record an explicit assessment; evidence must be referenced, never inferred."""
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            raise ValueError("hypothesis_id must be a non-empty string")
        if not isinstance(disposition, str) or disposition not in _DISPOSITIONS:
            raise ValueError(f"disposition must be one of {sorted(_DISPOSITIONS)}")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("reviewer must be a non-empty string")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("rationale must be a non-empty string")
        if isinstance(evidence_event_ids, (str, bytes)):
            raise TypeError("evidence_event_ids must be an iterable of event IDs")
        try:
            evidence = tuple(evidence_event_ids)
        except TypeError as exc:
            raise TypeError("evidence_event_ids must be an iterable of event IDs") from exc
        if not evidence or any(not isinstance(item, str) or not item.strip() for item in evidence):
            raise ValueError("at least one non-empty evidence event ID is required")
        if len(set(evidence)) != len(evidence):
            raise ValueError("evidence event IDs must be unique")

        with self._lock:
            hypothesis = self._hypotheses.get(hypothesis_id)
            if hypothesis is None:
                raise KeyError(f"unknown or evicted hypothesis: {hypothesis_id}")
            assessment = HypothesisAssessment(
                assessment_id=self._next_assessment_id,
                hypothesis_id=hypothesis_id,
                disposition=disposition,
                evidence_event_ids=evidence,
                reviewer=reviewer.strip(),
                rationale=rationale.strip(),
                assessed_at_iso=datetime.now(timezone.utc).isoformat(),
            )
            self._next_assessment_id += 1
            self._total_assessments += 1
            self._assessments.append(assessment)
            self._hypotheses[hypothesis_id] = replace(hypothesis, disposition=disposition)
            return assessment

    def snapshot(self) -> HypothesisRegistrySnapshot:
        with self._lock:
            return HypothesisRegistrySnapshot(
                hypotheses=tuple(self._hypotheses.values()),
                assessments=tuple(self._assessments),
                total_registered=self._total_registered,
                total_assessments=self._total_assessments,
            )
