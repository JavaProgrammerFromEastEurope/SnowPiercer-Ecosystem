from dataclasses import replace

import pytest

from kernel.command.events import (
    CommandEvent, CommandEventType, DiagnosticEvidenceTaskClosureVerifier,
    DiagnosticEvidenceTaskTracker, DiagnosticHypothesis, DiagnosticInvestigationClosureReporter,
    EvidenceCollectionPlan, EvidenceCollectionTask, HypothesisEvidencePlan, HypothesisRegistrySnapshot,
)
from datetime import datetime, timedelta, timezone


def _event(event_id, event_type, *, payload=None):
    return CommandEvent(event_id, "cmd-1", event_type,
                        datetime.now(timezone.utc) - timedelta(minutes=2), payload or {})


def _hypothesis(disposition="evidence_supports", hypothesis_id="h-1"):
    return DiagnosticHypothesis(
        hypothesis_id=hypothesis_id, diagnostic_event_id="diag-1", command_id="cmd-1",
        diagnostic_code="disk_fault", pattern_code="started_then_failed",
        observed_event_types=("command_started", "command_failed"),
        evidence_note="Observed failure sequence", analyzer_confidence="medium",
        disposition=disposition,
    )


def _snapshots(*, state="completed", disposition="evidence_supports", required=True, history_complete=True):
    task = EvidenceCollectionTask("collect_events", "normal", "Collect source events", required)
    plan = EvidenceCollectionPlan(1, 1, 0,
        (HypothesisEvidencePlan("h-1", "needs_more_evidence", (task,)),), history_complete, ())
    tracker = DiagnosticEvidenceTaskTracker()
    registered = tracker.register_plan(plan)[0]
    if state in {"completed", "blocked"}:
        tracker.start(registered.task_id, actor="worker")
        if state == "completed":
            tracker.complete(registered.task_id, actor="worker", result_note="Retrieved source events",
                             evidence_event_ids=("evt-1",))
        else:
            tracker.fail(registered.task_id, actor="worker", reason="Source unavailable", retryable=False)
    hypotheses = HypothesisRegistrySnapshot((_hypothesis(disposition),), (), 1, 0)
    events = (
        _event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC, payload={"code": "disk_fault"}),
        _event("evt-1", CommandEventType.COMMAND_FAILED),
    )
    tasks = tracker.snapshot()
    closure = DiagnosticEvidenceTaskClosureVerifier().verify(
        tasks, hypotheses, events, history_complete=history_complete)
    return tasks, hypotheses, closure


def test_all_verified_tasks_and_explicit_assessment_are_ready_for_expert_review():
    tasks, hypotheses, closure = _snapshots()
    report = DiagnosticInvestigationClosureReporter().report(tasks, hypotheses, closure)
    assert report.hypotheses[0].status == "ready_for_expert_review"
    assert report.ready_for_expert_review_count == 1
    assert report.all_investigations_ready_for_expert_review
    assert "not proof" in report.hypotheses[0].recommendation


def test_unassessed_hypothesis_is_not_automatically_resolved():
    tasks, hypotheses, closure = _snapshots(disposition="under_review")
    report = DiagnosticInvestigationClosureReporter().report(tasks, hypotheses, closure)
    assert report.hypotheses[0].status == "needs_review"
    assert not report.all_investigations_ready_for_expert_review


def test_open_task_prevents_investigation_readiness():
    tasks, hypotheses, closure = _snapshots(state="pending")
    report = DiagnosticInvestigationClosureReporter().report(tasks, hypotheses, closure)
    assert report.hypotheses[0].status == "open_tasks"
    assert report.open_count == 1
    assert report.hypotheses[0].outstanding_task_ids


def test_blocked_task_takes_precedence_over_other_statuses():
    tasks, hypotheses, closure = _snapshots(state="blocked")
    report = DiagnosticInvestigationClosureReporter().report(tasks, hypotheses, closure)
    assert report.hypotheses[0].status == "blocked"
    assert report.blocked_count == 1


def test_incomplete_history_never_reports_ready():
    tasks, hypotheses, closure = _snapshots(history_complete=False)
    report = DiagnosticInvestigationClosureReporter().report(tasks, hypotheses, closure)
    assert report.hypotheses[0].status == "needs_review"
    assert not report.all_investigations_ready_for_expert_review


def test_hypothesis_without_tasks_is_unplanned():
    tasks, hypotheses, closure = _snapshots()
    empty_tracker = replace(tasks, tasks=(), transitions=(), pending_count=0, in_progress_count=0,
                            completed_count=0, blocked_count=0)
    empty_closure = DiagnosticEvidenceTaskClosureVerifier().verify(
        empty_tracker, hypotheses, (_event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
        payload={"code": "disk_fault"}), _event("evt-1", CommandEventType.COMMAND_FAILED)), history_complete=True)
    report = DiagnosticInvestigationClosureReporter().report(empty_tracker, hypotheses, empty_closure)
    assert report.hypotheses[0].status == "unplanned"
    assert report.unplanned_count == 1


def test_report_rejects_mismatched_task_inventory_and_invalid_arguments():
    tasks, hypotheses, closure = _snapshots()
    reporter = DiagnosticInvestigationClosureReporter()
    with pytest.raises(ValueError, match="task IDs"):
        reporter.report(replace(tasks, tasks=()), hypotheses, closure)
    with pytest.raises(TypeError):
        reporter.report(object(), hypotheses, closure)


def test_task_for_missing_hypothesis_is_reported_as_orphan_not_silently_dropped():
    tasks, hypotheses, closure = _snapshots()
    orphaned = replace(tasks.tasks[0], hypothesis_id="evicted-hypothesis")
    orphan_snapshot = replace(tasks, tasks=(orphaned,))
    orphan_closure = DiagnosticEvidenceTaskClosureVerifier().verify(
        orphan_snapshot, hypotheses,
        (_event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
                payload={"code": "disk_fault"}), _event("evt-1", CommandEventType.COMMAND_FAILED)),
        history_complete=True,
    )
    report = DiagnosticInvestigationClosureReporter().report(orphan_snapshot, hypotheses, orphan_closure)
    assert report.orphan_task_ids == (orphaned.task_id,)
    assert not report.all_investigations_ready_for_expert_review
