from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventType, DiagnosticEvidenceTaskClosureVerifier,
    DiagnosticEvidenceTaskTracker, EvidenceCollectionPlan, EvidenceCollectionTask,
    HypothesisEvidencePlan, DiagnosticHypothesis, HypothesisRegistrySnapshot,
)


def _event(event_id, event_type, *, command_id="cmd-1", payload=None, timestamp=None):
    return CommandEvent(event_id, command_id, event_type,
                        timestamp or datetime.now(timezone.utc) - timedelta(minutes=2), payload or {})


def _hypothesis_snapshot():
    hypothesis = DiagnosticHypothesis(
        hypothesis_id="h-1", diagnostic_event_id="diag-1", command_id="cmd-1",
        diagnostic_code="disk_fault", pattern_code="started_then_failed",
        observed_event_types=("command_started", "command_failed"),
        evidence_note="Observed failure sequence", analyzer_confidence="medium",
    )
    return HypothesisRegistrySnapshot((hypothesis,), (), 1, 0)


def _completed_task(evidence_ids=("evt-1",), required=True):
    task = EvidenceCollectionTask("collect_events", "normal", "Collect event evidence", required)
    plan = EvidenceCollectionPlan(1, 1, 0,
        (HypothesisEvidencePlan("h-1", "needs_more_evidence", (task,)),), True, ())
    tracker = DiagnosticEvidenceTaskTracker()
    registered = tracker.register_plan(plan)[0]
    tracker.start(registered.task_id, actor="worker")
    tracker.complete(registered.task_id, actor="worker", result_note="Retrieved source events",
                     evidence_event_ids=evidence_ids)
    return tracker.snapshot()


def _events(*, evidence_command="cmd-1", evidence_time=None):
    return (
        _event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
               payload={"code": "disk_fault"}),
        _event("evt-1", CommandEventType.COMMAND_FAILED, command_id=evidence_command,
               timestamp=evidence_time),
    )


def test_completed_task_with_valid_evidence_and_complete_history_is_verified():
    report = DiagnosticEvidenceTaskClosureVerifier().verify(
        _completed_task(), _hypothesis_snapshot(), _events(), history_complete=True)
    assert report.verified_count == 1
    assert report.all_closed_and_verified
    assert report.results[0].verified_evidence_event_ids == ("evt-1",)
    assert report.results[0].findings == ()


def test_missing_task_evidence_blocks_closure_when_history_is_complete():
    report = DiagnosticEvidenceTaskClosureVerifier().verify(
        _completed_task(("missing",)), _hypothesis_snapshot(), _events(), history_complete=True)
    result = report.results[0]
    assert result.status == "blocked"
    assert "missing_task_evidence_event" in {item.code for item in result.findings}
    assert not report.all_closed_and_verified


def test_incomplete_history_requires_review_even_when_reference_is_present():
    report = DiagnosticEvidenceTaskClosureVerifier().verify(
        _completed_task(), _hypothesis_snapshot(), _events(), history_complete=False)
    assert report.results[0].status == "needs_review"
    assert report.needs_review_count == 1


def test_cross_command_evidence_is_warning_not_silent_acceptance():
    report = DiagnosticEvidenceTaskClosureVerifier().verify(
        _completed_task(), _hypothesis_snapshot(), _events(evidence_command="other-command"),
        history_complete=True)
    result = report.results[0]
    assert result.status == "needs_review"
    assert "cross_command_task_evidence" in {item.code for item in result.findings}


def test_evidence_timestamp_after_completion_blocks_closure():
    snapshot = _completed_task()
    task = snapshot.tasks[0]
    future = datetime.now(timezone.utc) + timedelta(days=1)
    events = _events(evidence_time=future)
    report = DiagnosticEvidenceTaskClosureVerifier().verify(
        snapshot, _hypothesis_snapshot(), events, history_complete=True)
    assert "evidence_after_task_completion" in {item.code for item in report.results[0].findings}
    assert report.blocked_count == 1


def test_open_task_is_not_mistaken_for_verified_closure():
    task = EvidenceCollectionTask("collect_events", "normal", "Collect event evidence", True)
    plan = EvidenceCollectionPlan(1, 1, 0,
        (HypothesisEvidencePlan("h-1", "needs_more_evidence", (task,)),), True, ())
    tracker = DiagnosticEvidenceTaskTracker()
    tracker.register_plan(plan)
    report = DiagnosticEvidenceTaskClosureVerifier().verify(
        tracker.snapshot(), _hypothesis_snapshot(), _events(), history_complete=True)
    assert report.open_task_count == 1
    assert report.results[0].status == "open"
    assert not report.all_closed_and_verified


def test_duplicate_inventory_id_and_invalid_inputs_are_reported_or_rejected():
    duplicate = _events() + (_events()[1],)
    report = DiagnosticEvidenceTaskClosureVerifier().verify(
        _completed_task(), _hypothesis_snapshot(), duplicate, history_complete=True)
    assert report.results[0].status == "blocked"
    verifier = DiagnosticEvidenceTaskClosureVerifier()
    with pytest.raises(TypeError):
        verifier.verify(object(), _hypothesis_snapshot(), _events())
    with pytest.raises(TypeError):
        verifier.verify(_completed_task(), _hypothesis_snapshot(), "not events")
