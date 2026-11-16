from datetime import datetime, timedelta, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventType, DiagnosticEvidenceReadinessAssessor,
    DiagnosticEvidenceValidator, DiagnosticHypothesisRegistry,
    ExecutionEventSequenceAnalyzer, ExecutionEventTimelineAnalysis,
    DiagnosticTimelineContext,
)


def _event(event_id, event_type, *, command_id="cmd-1", payload=None, seconds_ago=30):
    return CommandEvent(event_id, command_id, event_type,
                        datetime.now(timezone.utc) - timedelta(seconds=seconds_ago), payload or {})


def _registry():
    context = DiagnosticTimelineContext(
        diagnostic_event_id="diag-1", command_id="cmd-1", diagnostic_code="integrity_mismatch",
        diagnostic_timestamp_iso=datetime.now(timezone.utc).isoformat(),
        preceding_event_ids=("start-1", "fail-1"),
        preceding_event_types=("command_started", "command_failed"),
        elapsed_seconds_from_previous_event=1.0, evidence_note="observed sequence only",
    )
    analysis = ExecutionEventTimelineAnalysis(analyzed_events=2, diagnostic_count=1, contexts=(context,))
    registry = DiagnosticHypothesisRegistry()
    hypothesis = registry.register_findings(ExecutionEventSequenceAnalyzer().analyze(analysis).findings)[0]
    return registry, hypothesis


def _events():
    return (
        _event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
               payload={"code": "integrity_mismatch"}, seconds_ago=5),
        _event("start-1", CommandEventType.COMMAND_STARTED, seconds_ago=20),
        _event("fail-1", CommandEventType.COMMAND_FAILED, seconds_ago=10),
    )


def test_ready_requires_complete_history_diverse_present_evidence_and_explicit_review():
    registry, hypothesis = _registry()
    registry.assess(hypothesis.hypothesis_id, "evidence_supports", ("start-1", "fail-1"),
                    "reviewer", "Two event types are present; cause still requires independent review.")
    report = DiagnosticEvidenceReadinessAssessor().assess(registry.snapshot(), _events(), history_complete=True)
    assert report.ready_for_expert_review == 1
    assert report.results[0].status == "ready_for_expert_review"
    assert report.results[0].distinct_evidence_types == ("command_failed", "command_started")


def test_incomplete_history_never_reports_ready():
    registry, hypothesis = _registry()
    registry.assess(hypothesis.hypothesis_id, "evidence_supports", ("start-1", "fail-1"), "reviewer", "Review.")
    report = DiagnosticEvidenceReadinessAssessor().assess(registry.snapshot(), _events())
    assert report.needs_more_evidence == 1
    assert report.results[0].status == "needs_more_evidence"


def test_single_event_or_single_type_is_insufficient():
    registry, hypothesis = _registry()
    registry.assess(hypothesis.hypothesis_id, "evidence_supports", ("start-1",), "reviewer", "Review.")
    report = DiagnosticEvidenceReadinessAssessor().assess(registry.snapshot(), _events(), history_complete=True)
    assert report.results[0].status == "needs_more_evidence"
    assert any("two distinct" in item for item in report.results[0].recommendations)


def test_integrity_error_blocks_readiness():
    registry, hypothesis = _registry()
    registry.assess(hypothesis.hypothesis_id, "evidence_supports", ("start-1", "fail-1"), "reviewer", "Review.")
    bad_events = tuple(e for e in _events() if e.event_id != "diag-1") + (
        _event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
               payload={"code": "wrong_code"}),
    )
    report = DiagnosticEvidenceReadinessAssessor().assess(registry.snapshot(), bad_events, history_complete=True)
    assert report.blocked_by_integrity_issues == 1
    assert "diagnostic_code_mismatch" in report.results[0].issue_codes


def test_under_review_and_insufficient_evidence_are_not_ready():
    registry, hypothesis = _registry()
    registry.assess(hypothesis.hypothesis_id, "insufficient_evidence", ("start-1", "fail-1"), "reviewer", "Need more data.")
    report = DiagnosticEvidenceReadinessAssessor().assess(registry.snapshot(), _events(), history_complete=True)
    assert report.results[0].status == "needs_more_evidence"


def test_input_contracts_are_validated():
    assessor = DiagnosticEvidenceReadinessAssessor()
    registry, _ = _registry()
    with pytest.raises(TypeError):
        assessor.assess(object(), ())
    with pytest.raises(TypeError):
        assessor.assess(registry.snapshot(), (object(),))
    with pytest.raises(TypeError):
        assessor.assess(registry.snapshot(), (), history_complete=1)
    with pytest.raises(TypeError):
        DiagnosticEvidenceReadinessAssessor(validator=object())


def test_assessor_does_not_mutate_registry_or_events():
    registry, hypothesis = _registry()
    registry.assess(hypothesis.hypothesis_id, "evidence_supports", ("start-1", "fail-1"), "reviewer", "Review.")
    before = registry.snapshot()
    events = _events()
    DiagnosticEvidenceReadinessAssessor().assess(before, events, history_complete=True)
    assert registry.snapshot() == before
    assert len(events) == 3
