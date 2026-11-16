from datetime import datetime, timedelta, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventType, DiagnosticEvidenceValidator,
    DiagnosticHypothesisRegistry, ExecutionEventSequenceAnalyzer,
    ExecutionEventTimelineAnalysis, DiagnosticTimelineContext,
)


def _event(event_id, command_id="cmd-1", seconds_ago=30):
    event_type = (CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC
                  if event_id == "diag-1" else CommandEventType.COMMAND_STARTED)
    payload = {"code": "integrity_mismatch"} if event_id == "diag-1" else {}
    return CommandEvent(event_id, command_id, event_type,
                        datetime.now(timezone.utc) - timedelta(seconds=seconds_ago), payload)


def _registry_with_assessment():
    context = DiagnosticTimelineContext(
        diagnostic_event_id="diag-1", command_id="cmd-1", diagnostic_code="integrity_mismatch",
        diagnostic_timestamp_iso=datetime.now(timezone.utc).isoformat(),
        preceding_event_ids=("start-1", "fail-1"), preceding_event_types=("command_started", "command_failed"),
        elapsed_seconds_from_previous_event=1.0, evidence_note="temporal correlation only",
    )
    sequence = ExecutionEventSequenceAnalyzer().analyze(ExecutionEventTimelineAnalysis(
        analyzed_events=2, diagnostic_count=1, contexts=(context,),
    ))
    registry = DiagnosticHypothesisRegistry()
    hypothesis = registry.register_findings(sequence.findings)[0]
    assessment = registry.assess(
        hypothesis.hypothesis_id, "insufficient_evidence", ("start-1",),
        "reviewer-1", "Available events do not establish causation.",
    )
    return registry, hypothesis, assessment


def test_validates_present_references_and_flags_incomplete_history_only():
    registry, _, _ = _registry_with_assessment()
    result = DiagnosticEvidenceValidator().validate(registry.snapshot(), (_event("diag-1"), _event("start-1")))
    assert result.is_consistent and result.error_count == 0
    assert result.warning_count == 1
    assert result.issues[0].code == "history_may_be_incomplete"


def test_missing_evidence_severity_depends_on_history_completeness():
    registry, _, _ = _registry_with_assessment()
    validator = DiagnosticEvidenceValidator()
    partial = validator.validate(registry.snapshot(), (_event("diag-1"),))
    complete = validator.validate(registry.snapshot(), (_event("diag-1"),), history_complete=True)
    assert any(i.code == "missing_evidence_event" and i.severity == "warning" for i in partial.issues)
    assert any(i.code == "missing_evidence_event" and i.severity == "error" for i in complete.issues)


def test_rejects_duplicate_event_ids_as_ambiguous():
    registry, _, _ = _registry_with_assessment()
    result = DiagnosticEvidenceValidator().validate(
        registry.snapshot(), (_event("diag-1"), _event("diag-1"), _event("start-1")), history_complete=True,
    )
    assert any(i.code == "duplicate_event_id" for i in result.issues)
    assert not result.is_consistent


def test_cross_command_evidence_is_warning_not_automatic_causal_rejection():
    registry, _, _ = _registry_with_assessment()
    result = DiagnosticEvidenceValidator().validate(
        registry.snapshot(), (_event("diag-1"), _event("start-1", command_id="cmd-other")), history_complete=True,
    )
    issue = next(i for i in result.issues if i.code == "cross_command_evidence")
    assert issue.severity == "warning" and result.is_consistent


def test_rejects_event_that_postdates_assessment():
    registry, _, assessment = _registry_with_assessment()
    future = CommandEvent(
        "start-1", "cmd-1", CommandEventType.COMMAND_STARTED,
        datetime.fromisoformat(assessment.assessed_at_iso) + timedelta(seconds=5), {},
    )
    result = DiagnosticEvidenceValidator().validate(
        registry.snapshot(), (_event("diag-1"), future), history_complete=True,
    )
    assert any(i.code == "evidence_after_assessment" for i in result.issues)
    assert not result.is_consistent



def test_detects_originating_diagnostic_code_mismatch():
    registry, _, _ = _registry_with_assessment()
    wrong_diagnostic = CommandEvent(
        "diag-1", "cmd-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
        datetime.now(timezone.utc) - timedelta(seconds=10), {"code": "different_code"},
    )
    result = DiagnosticEvidenceValidator().validate(
        registry.snapshot(), (wrong_diagnostic, _event("start-1")), history_complete=True,
    )
    assert any(issue.code == "diagnostic_code_mismatch" for issue in result.issues)
    assert not result.is_consistent


def test_validates_inputs_and_timezone_awareness():
    registry, _, _ = _registry_with_assessment()
    validator = DiagnosticEvidenceValidator()
    with pytest.raises(TypeError):
        validator.validate(object(), ())
    with pytest.raises(TypeError):
        validator.validate(registry.snapshot(), (object(),))
    with pytest.raises(TypeError):
        validator.validate(registry.snapshot(), (), history_complete=1)
    assert validator._parse_aware("2026-10-20T10:00:00") is None
