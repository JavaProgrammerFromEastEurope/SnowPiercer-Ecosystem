from dataclasses import replace

from kernel.command.events import (
    CommandEvent, CommandEventType, DiagnosticEvidenceTaskClosureVerifier,
    DiagnosticInvestigationClosureReporter,
)
from tests.stage61.test_diagnostic_investigation_closure import _event, _snapshots


def _recovery_case():
    task_snapshot, hypotheses, _ = _snapshots(state="pending")
    interrupted = replace(task_snapshot.tasks[0], state="recovery_required", result_note="Interrupted")
    task_snapshot = replace(
        task_snapshot, tasks=(interrupted,), pending_count=0, in_progress_count=0,
        completed_count=0, recovery_required_count=1,
    )
    events = (
        _event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC, payload={"code": "disk_fault"}),
        _event("evt-1", CommandEventType.COMMAND_FAILED),
    )
    closure = DiagnosticEvidenceTaskClosureVerifier().verify(
        task_snapshot, hypotheses, events, history_complete=True,
    )
    return task_snapshot, hypotheses, closure


def test_recovery_required_task_has_explicit_unresolved_finding_and_blocks_closure():
    tasks, hypotheses, closure = _recovery_case()
    result = closure.results[0]
    assert result.state == "recovery_required"
    assert result.status == "open"
    assert "interrupted_task_recovery_unresolved" in {finding.code for finding in result.findings}
    assert closure.recovery_required_count == 1
    assert not closure.all_closed_and_verified


def test_investigation_report_names_recovery_state_and_cannot_be_ready():
    tasks, hypotheses, closure = _recovery_case()
    report = DiagnosticInvestigationClosureReporter().report(tasks, hypotheses, closure)
    summary = report.hypotheses[0]
    assert summary.status == "recovery_required"
    assert summary.recovery_required_task_count == 1
    assert report.total_recovery_required_count == 1
    assert report.open_count == 1
    assert not report.all_investigations_ready_for_expert_review
    assert "external state" in summary.recommendation


def test_recovery_count_also_guards_aggregate_closure_property():
    tasks, hypotheses, closure = _snapshots()
    # Defensive check for callers constructing reports directly: a nonzero recovery
    # count cannot be overridden by otherwise clean closure counters.
    guarded = replace(closure, recovery_required_count=1)
    assert not guarded.all_closed_and_verified
