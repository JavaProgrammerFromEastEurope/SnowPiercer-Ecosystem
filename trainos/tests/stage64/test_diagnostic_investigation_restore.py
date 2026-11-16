import pytest

from kernel.command.events import (
    DiagnosticEvidenceTaskTracker,
    DiagnosticInvestigationCheckpointService,
    DiagnosticInvestigationStore,
    DiagnosticHypothesis,
    DiagnosticHypothesisRegistry,
    EvidenceCollectionTask,
    EvidenceTaskTrackerSnapshot,
    HypothesisAssessment,
    HypothesisRegistrySnapshot,
    InvestigationStoreIntegrityError,
    TrackedEvidenceTask,
    EvidenceTaskTransition,
)


def snapshots(*, state="pending", attempts=0):
    hypothesis = DiagnosticHypothesis(
        hypothesis_id="h1", diagnostic_event_id="e-diag", command_id="cmd1",
        diagnostic_code="E42", pattern_code="retry_then_failure",
        observed_event_types=("started", "failed"), evidence_note="observed sequence",
        analyzer_confidence="low", disposition="evidence_supports",
    )
    assessment = HypothesisAssessment(
        assessment_id=1, hypothesis_id="h1", disposition="evidence_supports",
        evidence_event_ids=("e-diag",), reviewer="reviewer", rationale="matches observation",
        assessed_at_iso="2026-10-20T10:00:00+00:00",
    )
    hs = HypothesisRegistrySnapshot((hypothesis,), (assessment,), 1, 1)
    task_def = EvidenceCollectionTask("recover_event", "high", "Recover event history", True)
    tracked = TrackedEvidenceTask(
        task_id="h1::recover_event", hypothesis_id="h1", task=task_def,
        state=state, attempts=attempts, max_attempts=3,
        result_note="started" if state == "in_progress" else "",
        evidence_event_ids=(), updated_at_iso="2026-10-20T10:00:00+00:00",
    )
    transitions = [EvidenceTaskTransition(1, tracked.task_id, None, "pending", "planner",
                                           "task registered", "2026-10-20T10:00:00+00:00")]
    if state == "in_progress":
        transitions.append(EvidenceTaskTransition(2, tracked.task_id, "pending", "in_progress", "operator",
                                                  "Task started", "2026-10-20T10:01:00+00:00"))
    ts = EvidenceTaskTrackerSnapshot(
        (tracked,), tuple(transitions), 1, len(transitions),
        int(state == "pending"), int(state == "in_progress"), 0, 0, 0,
    )
    return hs, ts


def test_restore_returns_fresh_typed_instances_and_preserves_state(tmp_path):
    h, t = snapshots(state="in_progress", attempts=1)
    with DiagnosticInvestigationStore(tmp_path / "restore.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case", h, t)
        restored = service.restore_checkpoint("case")
    assert restored is not None
    assert isinstance(restored.hypothesis_registry, DiagnosticHypothesisRegistry)
    assert isinstance(restored.task_tracker, DiagnosticEvidenceTaskTracker)
    assert restored.hypothesis_registry.snapshot() == h
    assert restored.task_tracker.snapshot() == t
    # Recovery does not silently retry a task that was in progress at process shutdown.
    assert restored.task_tracker.snapshot().tasks[0].state == "in_progress"


def test_restored_instances_continue_without_replaying_in_progress_task(tmp_path):
    h, t = snapshots(state="in_progress", attempts=1)
    with DiagnosticInvestigationStore(tmp_path / "restore.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case", h, t)
        restored = service.restore_checkpoint("case")
    task_id = restored.task_tracker.snapshot().tasks[0].task_id
    completed = restored.task_tracker.complete(
        task_id, actor="operator", result_note="evidence recovered", evidence_event_ids=("e-recovered",)
    )
    assert completed.state == "completed"
    next_assessment = restored.hypothesis_registry.assess(
        "h1", "insufficient_evidence", ("e-recovered",), "reviewer-2", "additional evidence needs review"
    )
    assert next_assessment.assessment_id == 2
    assert restored.hypothesis_registry.snapshot().hypotheses[0].disposition == "insufficient_evidence"


def test_restore_missing_checkpoint_returns_none(tmp_path):
    with DiagnosticInvestigationStore(tmp_path / "restore.db") as store:
        assert DiagnosticInvestigationCheckpointService(store).restore_checkpoint("missing") is None


def test_restore_rejects_checkpoint_exceeding_configured_capacity(tmp_path):
    h, t = snapshots()
    with DiagnosticInvestigationStore(tmp_path / "restore.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case", h, t)
        with pytest.raises(InvestigationStoreIntegrityError, match="capacity"):
            service.restore_checkpoint("case", max_hypotheses=1, max_tasks=1, max_attempts=2)


def test_restore_rejects_attempt_count_mismatch_with_transition_history(tmp_path):
    h, t = snapshots(state="in_progress", attempts=0)
    with DiagnosticInvestigationStore(tmp_path / "restore.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        with pytest.raises(InvestigationStoreIntegrityError, match="attempts disagree"):
            service.save_checkpoint("case", h, t)
        assert service.load_checkpoint("case") is None


def test_restore_rejects_discontinuous_transition_history(tmp_path):
    h, t = snapshots(state="in_progress", attempts=1)
    broken = list(t.transitions)
    broken[1] = EvidenceTaskTransition(2, broken[1].task_id, "blocked", "in_progress", "operator",
                                       "Task started", "2026-10-20T10:01:00+00:00")
    t_bad = EvidenceTaskTrackerSnapshot(t.tasks, tuple(broken), t.total_registered, t.total_transitions,
                                        t.pending_count, t.in_progress_count, t.completed_count, t.blocked_count)
    with DiagnosticInvestigationStore(tmp_path / "restore.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        with pytest.raises(InvestigationStoreIntegrityError, match="invalid task transition|discontinuous"):
            service.save_checkpoint("case", h, t_bad)
        assert service.load_checkpoint("case") is None


def test_restore_rejects_hypothesis_assessment_disposition_mismatch(tmp_path):
    h, t = snapshots()
    bad_hypothesis = DiagnosticHypothesis(
        hypothesis_id="h1", diagnostic_event_id="e-diag", command_id="cmd1",
        diagnostic_code="E42", pattern_code="retry_then_failure",
        observed_event_types=("started", "failed"), evidence_note="observed sequence",
        analyzer_confidence="low", disposition="under_review",
    )
    h_bad = HypothesisRegistrySnapshot((bad_hypothesis,), h.assessments, 1, 1)
    with DiagnosticInvestigationStore(tmp_path / "restore.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        with pytest.raises(InvestigationStoreIntegrityError, match="disagrees"):
            service.save_checkpoint("case", h_bad, t)
        assert service.load_checkpoint("case") is None


def test_restore_rejects_invalid_restore_options(tmp_path):
    h, t = snapshots()
    with DiagnosticInvestigationStore(tmp_path / "restore.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case", h, t)
        with pytest.raises(ValueError, match="max_tasks"):
            service.restore_checkpoint("case", max_tasks=0)
