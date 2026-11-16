import pytest
from kernel.command.events import DiagnosticEvidenceTaskTracker, DiagnosticInvestigationCheckpointService, DiagnosticInvestigationStore
from tests.stage64.test_diagnostic_investigation_restore import snapshots


def tracker_with_interrupted_task():
    h, snap = snapshots(state="in_progress", attempts=1)
    tracker = DiagnosticEvidenceTaskTracker(max_tasks=10, max_attempts=3)
    tracker._tasks = {item.task_id: item for item in snap.tasks}
    tracker._transitions = list(snap.transitions)
    tracker._total_registered = snap.total_registered
    tracker._total_transitions = snap.total_transitions
    return tracker, snap.tasks[0].task_id


def test_restart_marks_interrupted_task_recovery_required_without_retry():
    tracker, task_id = tracker_with_interrupted_task()
    recovered = tracker.mark_interrupted_tasks_for_recovery()
    assert len(recovered) == 1
    assert recovered[0].state == "recovery_required"
    assert recovered[0].attempts == 1
    assert tracker.snapshot().recovery_required_count == 1
    with pytest.raises(ValueError, match="pending state"):
        tracker.start(task_id, actor="operator")


def test_explicit_retry_decision_returns_task_to_pending():
    tracker, task_id = tracker_with_interrupted_task()
    tracker.mark_interrupted_tasks_for_recovery()
    result = tracker.resolve_recovery_required(task_id, decision="retry", actor="operator", note="checked external state")
    assert result.state == "pending"
    assert result.attempts == 1
    assert tracker.snapshot().transitions[-1].to_state == "pending"


def test_explicit_block_decision_blocks_task():
    tracker, task_id = tracker_with_interrupted_task()
    tracker.mark_interrupted_tasks_for_recovery()
    result = tracker.resolve_recovery_required(task_id, decision="block", actor="operator", note="unsafe to retry")
    assert result.state == "blocked"


def test_retry_is_refused_when_attempt_limit_exhausted():
    tracker, task_id = tracker_with_interrupted_task()
    task = tracker._tasks[task_id]
    from dataclasses import replace
    tracker._tasks[task_id] = replace(task, attempts=3, max_attempts=3)
    # Fixture's history records only one start; this method's decision gate is still tested directly.
    tracker._tasks[task_id] = replace(tracker._tasks[task_id], state="recovery_required")
    with pytest.raises(ValueError, match="retry limit exhausted"):
        tracker.resolve_recovery_required(task_id, decision="retry", actor="operator", note="retry requested")


def test_invalid_decision_does_not_mutate_task():
    tracker, task_id = tracker_with_interrupted_task()
    tracker.mark_interrupted_tasks_for_recovery()
    before = tracker.snapshot()
    with pytest.raises(ValueError, match="decision"):
        tracker.resolve_recovery_required(task_id, decision="auto", actor="operator", note="no")
    assert tracker.snapshot() == before


def test_recovery_state_survives_checkpoint_restore(tmp_path):
    h, t = snapshots(state="in_progress", attempts=1)
    tracker = DiagnosticEvidenceTaskTracker(max_tasks=10, max_attempts=3)
    tracker._tasks = {item.task_id: item for item in t.tasks}
    tracker._transitions = list(t.transitions)
    tracker._total_registered = t.total_registered
    tracker._total_transitions = t.total_transitions
    tracker.mark_interrupted_tasks_for_recovery()
    with DiagnosticInvestigationStore(tmp_path / "recover.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case", h, tracker.snapshot())
        restored = service.restore_checkpoint("case")
    assert restored.task_tracker.snapshot().tasks[0].state == "recovery_required"
    assert restored.task_tracker.snapshot().recovery_required_count == 1
