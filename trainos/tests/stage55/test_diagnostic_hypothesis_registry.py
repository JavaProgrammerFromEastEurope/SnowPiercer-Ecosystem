import pytest

from kernel.command.events import (
    DiagnosticHypothesisRegistry,
    ExecutionEventSequenceAnalyzer,
    ExecutionEventTimelineAnalysis,
    DiagnosticTimelineContext,
)


def finding(event_id="diag-1", pattern="started_then_failed"):
    context = DiagnosticTimelineContext(
        diagnostic_event_id=event_id,
        command_id="cmd-1",
        diagnostic_code="integrity_mismatch",
        diagnostic_timestamp_iso="2026-10-20T10:00:00+00:00",
        preceding_event_ids=("start-1", "fail-1"),
        preceding_event_types=("command_started", "command_failed"),
        elapsed_seconds_from_previous_event=1.0,
        evidence_note="temporal correlation only",
    )
    result = ExecutionEventSequenceAnalyzer().analyze(ExecutionEventTimelineAnalysis(
        analyzed_events=3, diagnostic_count=1, contexts=(context,),
    ))
    return next(item for item in result.findings if item.pattern_code == pattern)


def test_registration_creates_pending_hypothesis_and_is_idempotent():
    registry = DiagnosticHypothesisRegistry()
    first = registry.register_findings((finding(),))[0]
    again = registry.register_findings((finding(),))[0]
    snap = registry.snapshot()
    assert first.hypothesis_id == again.hypothesis_id
    assert first.disposition == "under_review"
    assert len(snap.hypotheses) == 1
    assert snap.total_registered == 1


def test_assessment_requires_explicit_evidence_and_updates_latest_disposition():
    registry = DiagnosticHypothesisRegistry()
    hypothesis = registry.register_findings((finding(),))[0]
    assessment = registry.assess(
        hypothesis.hypothesis_id, "insufficient_evidence", ("start-1", "fail-1"),
        "reviewer-1", "Events show order but do not identify root cause.",
    )
    snap = registry.snapshot()
    assert assessment.evidence_event_ids == ("start-1", "fail-1")
    assert snap.hypotheses[0].disposition == "insufficient_evidence"
    assert snap.assessments == (assessment,)


def test_multiple_assessments_preserve_history():
    registry = DiagnosticHypothesisRegistry()
    hypothesis = registry.register_findings((finding(),))[0]
    registry.assess(hypothesis.hypothesis_id, "under_review", ("e1",), "reviewer", "Need more logs")
    registry.assess(hypothesis.hypothesis_id, "evidence_supports", ("e1", "e2"), "reviewer", "Independent logs support this pattern")
    snap = registry.snapshot()
    assert len(snap.assessments) == 2
    assert snap.hypotheses[0].disposition == "evidence_supports"


def test_invalid_assessment_and_unknown_hypothesis_rejected():
    registry = DiagnosticHypothesisRegistry()
    hypothesis = registry.register_findings((finding(),))[0]
    with pytest.raises(ValueError):
        registry.assess(hypothesis.hypothesis_id, "proven_cause", ("e1",), "reviewer", "reason")
    with pytest.raises(ValueError):
        registry.assess(hypothesis.hypothesis_id, "evidence_supports", (), "reviewer", "reason")
    with pytest.raises(KeyError):
        registry.assess("missing", "under_review", ("e1",), "reviewer", "reason")


def test_bounded_retention_evicts_hypothesis_and_its_assessments():
    registry = DiagnosticHypothesisRegistry(max_hypotheses=1)
    first = registry.register_findings((finding("diag-1"),))[0]
    registry.assess(first.hypothesis_id, "under_review", ("e1",), "reviewer", "checking")
    second = registry.register_findings((finding("diag-2"),))[0]
    snap = registry.snapshot()
    assert [h.hypothesis_id for h in snap.hypotheses] == [second.hypothesis_id]
    assert snap.assessments == ()
    assert snap.total_registered == 2
    assert snap.total_assessments == 1


def test_validates_registry_limit_and_finding_types():
    with pytest.raises(ValueError):
        DiagnosticHypothesisRegistry(max_hypotheses=True)
    with pytest.raises(TypeError):
        DiagnosticHypothesisRegistry().register_findings((object(),))
