"""Cross-stage integration checks for interrupted diagnostic evidence tasks."""
from kernel.command.events import (
    CommandEventType, DiagnosticEvidenceTaskClosureVerifier,
    DiagnosticEvidenceTaskTracker, DiagnosticInvestigationCheckpointService,
    DiagnosticInvestigationStore, DiagnosticInvestigationClosureReporter,
)
from tests.stage64.test_diagnostic_investigation_restore import snapshots
from tests.stage61.test_diagnostic_investigation_closure import _event


def _recovery_snapshot():
    hypotheses, tasks = snapshots(state="in_progress", attempts=1)
    tracker = DiagnosticEvidenceTaskTracker(max_tasks=10, max_attempts=3)
    tracker._tasks = {task.task_id: task for task in tasks.tasks}
    tracker._transitions = list(tasks.transitions)
    tracker._total_registered = tasks.total_registered
    tracker._total_transitions = tasks.total_transitions
    tracker.mark_interrupted_tasks_for_recovery(actor="stage71_test")
    return hypotheses, tracker.snapshot()


def _closure(restored):
    task_snapshot = restored.task_tracker.snapshot()
    events = (
        _event("diag-1", CommandEventType.EXECUTION_INTEGRITY_DIAGNOSTIC,
               payload={"code": "E42"}),
        _event("evt-1", CommandEventType.COMMAND_FAILED),
    )
    result = DiagnosticEvidenceTaskClosureVerifier().verify(
        task_snapshot, restored.hypothesis_registry.snapshot(), events, history_complete=True,
    )
    return DiagnosticInvestigationClosureReporter().report(
        task_snapshot, restored.hypothesis_registry.snapshot(), result,
    )


def test_recovery_required_survives_database_restart_and_assessed_restore(tmp_path):
    hypotheses, tasks = _recovery_snapshot()
    db = tmp_path / "stage71.db"
    with DiagnosticInvestigationStore(db) as store:
        DiagnosticInvestigationCheckpointService(store).save_checkpoint("case", hypotheses, tasks)

    with DiagnosticInvestigationStore(db) as store:
        assessment = DiagnosticInvestigationCheckpointService(store).restore_checkpoint_with_assessment("case")

    assert assessment.is_successful
    assert assessment.integrity_report.is_consistent
    restored_tasks = assessment.restored.task_tracker.snapshot()
    assert restored_tasks.tasks[0].state == "recovery_required"
    assert restored_tasks.recovery_required_count == 1
    assert restored_tasks.tasks[0].attempts == 1


def test_recovery_required_after_restart_prevents_closure_readiness(tmp_path):
    hypotheses, tasks = _recovery_snapshot()
    db = tmp_path / "stage71.db"
    with DiagnosticInvestigationStore(db) as store:
        DiagnosticInvestigationCheckpointService(store).save_checkpoint("case", hypotheses, tasks)
    with DiagnosticInvestigationStore(db) as store:
        assessment = DiagnosticInvestigationCheckpointService(store).restore_checkpoint_with_assessment("case")

    report = _closure(assessment.restored)
    assert not report.all_investigations_ready_for_expert_review
    assert report.total_recovery_required_count == 1
    assert report.hypotheses[0].status == "recovery_required"


def test_explicit_block_decision_after_restart_is_recorded_and_closes_recovery_gate(tmp_path):
    hypotheses, tasks = _recovery_snapshot()
    db = tmp_path / "stage71.db"
    with DiagnosticInvestigationStore(db) as store:
        DiagnosticInvestigationCheckpointService(store).save_checkpoint("case", hypotheses, tasks)
    with DiagnosticInvestigationStore(db) as store:
        assessment = DiagnosticInvestigationCheckpointService(store).restore_checkpoint_with_assessment("case")

    tracker = assessment.restored.task_tracker
    task_id = tracker.snapshot().tasks[0].task_id
    blocked = tracker.resolve_recovery_required(
        task_id, decision="block", actor="operator", note="External state reviewed; retry unsafe",
    )
    assert blocked.state == "blocked"
    assert tracker.snapshot().recovery_required_count == 0
    assert tracker.snapshot().transitions[-1].actor == "operator"
    assert tracker.snapshot().transitions[-1].note == "recovery decision=block: External state reviewed; retry unsafe"
