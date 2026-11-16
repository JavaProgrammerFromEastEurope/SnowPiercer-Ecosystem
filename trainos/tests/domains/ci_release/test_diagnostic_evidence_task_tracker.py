from dataclasses import replace

import pytest

from kernel.command.events import (
    DiagnosticEvidenceTaskTracker, EvidenceCollectionPlan,
    EvidenceCollectionTask, HypothesisEvidencePlan,
)


def _plan(tasks=None):
    tasks = tasks or (
        EvidenceCollectionTask("recover_event", "high", "Recover source event", True),
        EvidenceCollectionTask("expert_review", "normal", "Request expert review", True),
    )
    return EvidenceCollectionPlan(1, len(tasks), sum(t.priority == "high" for t in tasks),
                                  (HypothesisEvidencePlan("h-1", "needs_more_evidence", tuple(tasks)),),
                                  False, ("history may be incomplete",))


def test_register_start_complete_and_snapshot_audit():
    tracker = DiagnosticEvidenceTaskTracker()
    registered = tracker.register_plan(_plan())
    task = next(item for item in registered if item.task.code == "recover_event")
    started = tracker.start(task.task_id, actor="operator")
    assert started.state == "in_progress" and started.attempts == 1
    completed = tracker.complete(task.task_id, actor="operator", result_note="Event retrieved", evidence_event_ids=("evt-1", "evt-2"))
    assert completed.state == "completed"
    snap = tracker.snapshot()
    assert snap.completed_count == 1 and snap.pending_count == 1
    assert [item.sequence for item in snap.transitions] == list(range(1, snap.total_transitions + 1))
    assert snap.transitions[-1].to_state == "completed"


def test_register_plan_is_idempotent_and_conflicts_are_rejected():
    tracker = DiagnosticEvidenceTaskTracker()
    first = tracker.register_plan(_plan())
    second = tracker.register_plan(_plan())
    assert first == second
    assert tracker.snapshot().total_registered == 2
    conflicting = _plan((EvidenceCollectionTask("recover_event", "normal", "Different definition", True),))
    with pytest.raises(ValueError):
        tracker.register_plan(conflicting)


def test_retryable_failure_requeues_until_attempt_limit_then_blocks():
    tracker = DiagnosticEvidenceTaskTracker(max_attempts=2)
    task = tracker.register_plan(_plan())[0]
    tracker.start(task.task_id, actor="worker")
    assert tracker.fail(task.task_id, actor="worker", reason="source unavailable").state == "pending"
    tracker.start(task.task_id, actor="worker")
    assert tracker.fail(task.task_id, actor="worker", reason="still unavailable").state == "blocked"
    assert tracker.snapshot().blocked_count == 1


def test_state_transitions_and_evidence_references_are_validated():
    tracker = DiagnosticEvidenceTaskTracker()
    task = tracker.register_plan(_plan())[0]
    with pytest.raises(ValueError):
        tracker.complete(task.task_id, actor="operator", result_note="done")
    tracker.start(task.task_id, actor="operator")
    with pytest.raises(ValueError):
        tracker.complete(task.task_id, actor="operator", result_note="done", evidence_event_ids=("e1", "e1"))
    with pytest.raises(TypeError):
        tracker.fail(task.task_id, actor="operator", reason="no", retryable=1)


def test_capacity_overflow_is_atomic_and_block_is_terminal():
    tracker = DiagnosticEvidenceTaskTracker(max_tasks=1)
    with pytest.raises(OverflowError):
        tracker.register_plan(_plan())
    assert tracker.snapshot().total_registered == 0
    one_task_plan = _plan((EvidenceCollectionTask("recover_event", "high", "Recover", True),))
    task = tracker.register_plan(one_task_plan)[0]
    tracker.block(task.task_id, actor="reviewer", reason="requires external authority")
    with pytest.raises(ValueError):
        tracker.start(task.task_id, actor="worker")
    assert tracker.snapshot().blocked_count == 1


def test_input_contracts():
    with pytest.raises(ValueError):
        DiagnosticEvidenceTaskTracker(max_tasks=0)
    with pytest.raises(ValueError):
        DiagnosticEvidenceTaskTracker(max_attempts=0)
    with pytest.raises(TypeError):
        DiagnosticEvidenceTaskTracker().register_plan(object())
