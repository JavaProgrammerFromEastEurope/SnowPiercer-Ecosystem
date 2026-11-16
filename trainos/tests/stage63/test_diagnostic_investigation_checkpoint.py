import pytest

from kernel.command.events import (
    DiagnosticInvestigationCheckpointService,
    DiagnosticInvestigationStore,
    DiagnosticHypothesis,
    HypothesisAssessment,
    HypothesisRegistrySnapshot,
    EvidenceCollectionTask,
    EvidenceTaskTrackerSnapshot,
    TrackedEvidenceTask,
    EvidenceTaskTransition,
    InvestigationRevisionConflict,
    InvestigationStoreIntegrityError,
)


def snapshots():
    hypothesis = DiagnosticHypothesis(
        hypothesis_id="h1", diagnostic_event_id="e-diag", command_id="cmd1",
        diagnostic_code="E42", pattern_code="retry_then_failure",
        observed_event_types=("started", "failed"), evidence_note="observed sequence",
        analyzer_confidence="low", disposition="under_review",
    )
    assessment = HypothesisAssessment(
        assessment_id=1, hypothesis_id="h1", disposition="under_review",
        evidence_event_ids=("e-diag",), reviewer="reviewer", rationale="needs review",
        assessed_at_iso="2026-10-20T10:00:00+00:00",
    )
    h_snapshot = HypothesisRegistrySnapshot((hypothesis,), (assessment,), 1, 1)
    task_def = EvidenceCollectionTask("recover_event", "high", "Recover event history", True)
    tracked = TrackedEvidenceTask(
        task_id="h1::recover_event", hypothesis_id="h1", task=task_def,
        state="pending", attempts=0, max_attempts=3, result_note="",
        evidence_event_ids=(), updated_at_iso="2026-10-20T10:00:00+00:00",
    )
    transition = EvidenceTaskTransition(1, tracked.task_id, None, "pending", "planner",
                                        "task registered", "2026-10-20T10:00:00+00:00")
    t_snapshot = EvidenceTaskTrackerSnapshot((tracked,), (transition,), 1, 1, 1, 0, 0, 0)
    return h_snapshot, t_snapshot


def test_checkpoint_round_trip_restores_typed_snapshots_after_restart(tmp_path):
    path = tmp_path / "investigations.db"
    h, t = snapshots()
    with DiagnosticInvestigationStore(path) as store:
        saved = DiagnosticInvestigationCheckpointService(store).save_checkpoint("case-1", h, t)
        assert saved.revision == 1
    with DiagnosticInvestigationStore(path) as store:
        loaded = DiagnosticInvestigationCheckpointService(store).load_checkpoint("case-1")
    assert loaded is not None
    assert loaded.hypotheses == h
    assert loaded.tasks == t
    assert loaded.checksum == saved.checksum


def test_checkpoint_versions_use_optimistic_concurrency(tmp_path):
    h, t = snapshots()
    with DiagnosticInvestigationStore(tmp_path / "store.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        assert service.save_checkpoint("case-1", h, t).revision == 1
        assert service.save_checkpoint("case-1", h, t, expected_revision=1).revision == 2
        with pytest.raises(InvestigationRevisionConflict):
            service.save_checkpoint("case-1", h, t, expected_revision=1)
        assert service.load_checkpoint("case-1").revision == 2


def test_checkpoint_rejects_task_reference_to_missing_hypothesis_before_write(tmp_path):
    h, t = snapshots()
    orphan = TrackedEvidenceTask("orphan", "missing-h", t.tasks[0].task)
    t_bad = EvidenceTaskTrackerSnapshot((orphan,), (), 1, 0, 1, 0, 0, 0)
    with DiagnosticInvestigationStore(tmp_path / "store.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        with pytest.raises(InvestigationStoreIntegrityError, match="absent hypothesis"):
            service.save_checkpoint("case-1", h, t_bad)
        assert service.load_checkpoint("case-1") is None


def test_checkpoint_rejects_inconsistent_task_state_counts(tmp_path):
    h, t = snapshots()
    bad = EvidenceTaskTrackerSnapshot(t.tasks, t.transitions, 1, 1, 0, 0, 1, 0)
    with DiagnosticInvestigationStore(tmp_path / "store.db") as store:
        with pytest.raises(InvestigationStoreIntegrityError, match="state counts"):
            DiagnosticInvestigationCheckpointService(store).save_checkpoint("case-1", h, bad)
        assert store.load("diagnostic_investigation_checkpoint", "case-1") is None


def test_missing_checkpoint_returns_none_and_blank_id_is_rejected(tmp_path):
    with DiagnosticInvestigationStore(tmp_path / "store.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        assert service.load_checkpoint("unknown") is None
        with pytest.raises(ValueError):
            service.load_checkpoint(" ")
