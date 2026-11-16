"""A restarted process must not repeat work whose external outcome is unknown."""
from dataclasses import replace

from kernel.command.events.diagnostic_evidence_collection_planner import EvidenceCollectionTask
from kernel.command.events.diagnostic_evidence_task_tracker import (
    EvidenceTaskTrackerSnapshot,
    TrackedEvidenceTask,
)
from kernel.command.events.interrupted_task_reconciliation import (
    InterruptedTaskObservation,
    InterruptedTaskReconciler,
)


def _snapshot(*, attempts: int = 1, state: str = "recovery_required"):
    task_id = "trainos-stage151::verify-external-outcome"
    task = TrackedEvidenceTask(
        task_id=task_id,
        hypothesis_id="trainos-stage151",
        task=EvidenceCollectionTask(
            code="verify_external_outcome",
            priority="high",
            description="Reconcile a command whose external result is unknown.",
            required_for_review=True,
        ),
        state=state,
        attempts=attempts,
        max_attempts=3,
        result_note="Process restarted before acknowledgement was received.",
        updated_at_iso="2026-10-23T10:00:00+00:00",
    )
    return EvidenceTaskTrackerSnapshot(
        tasks=(task,), transitions=(), total_registered=1, total_transitions=2,
        pending_count=int(state == "pending"),
        in_progress_count=int(state == "in_progress"),
        completed_count=int(state == "completed"),
        blocked_count=int(state == "blocked"),
        recovery_required_count=int(state == "recovery_required"),
    ), task_id


def _observation(task_id: str, status: str, *, observer: str = "independent-reviewer", note: str = "Compared authoritative execution records."):
    return InterruptedTaskObservation(
        task_id=task_id,
        observation_status=status,
        observed_at_iso="2026-10-23T10:05:00+00:00",
        observer=observer,
        note=note,
        evidence_ids=("external-audit-record-151",),
    )


def test_missing_observation_after_restart_keeps_task_quarantined():
    snapshot, task_id = _snapshot()

    report = InterruptedTaskReconciler().reconcile(snapshot, [])

    assessment = report.assessments[0]
    assert assessment.task_id == task_id
    assert assessment.recommendation == "keep_recovery_required"
    assert assessment.observed_status is None
    assert "observation_missing" in assessment.finding_codes
    assert snapshot.tasks[0].state == "recovery_required"
    assert snapshot.tasks[0].attempts == 1


def test_unknown_external_outcome_never_recommends_automatic_retry():
    snapshot, task_id = _snapshot()
    before = snapshot

    report = InterruptedTaskReconciler().reconcile(
        snapshot, [_observation(task_id, "partial_or_unknown")]
    )

    assessment = report.assessments[0]
    assert assessment.recommendation == "keep_recovery_required"
    assert assessment.observed_status == "partial_or_unknown"
    assert "outcome_ambiguous" in assessment.finding_codes
    assert snapshot == before


def test_claimed_completion_requires_independent_verification_and_is_not_applied():
    snapshot, task_id = _snapshot()

    report = InterruptedTaskReconciler().reconcile(
        snapshot, [_observation(task_id, "confirmed_completed")]
    )

    assessment = report.assessments[0]
    assert assessment.recommendation == "completed_outcome_requires_independent_verification"
    assert "completion_not_applied_automatically" in assessment.finding_codes
    assert snapshot.tasks[0].state == "recovery_required"
    assert snapshot.tasks[0].attempts == 1


def test_conflicting_observations_block_retry_even_if_one_says_not_started():
    snapshot, task_id = _snapshot()
    observations = (
        _observation(task_id, "confirmed_not_started", observer="reviewer-a"),
        _observation(task_id, "external_effect_detected", observer="reviewer-b"),
    )

    report = InterruptedTaskReconciler().reconcile(snapshot, observations)

    assessment = report.assessments[0]
    assert assessment.recommendation == "keep_recovery_required"
    assert "duplicate_observations" in assessment.finding_codes
    assert report.has_blocking_findings
    assert snapshot.tasks[0].state == "recovery_required"


def test_invalid_external_observation_cannot_be_used_as_retry_evidence():
    snapshot, task_id = _snapshot()
    invalid = _observation(task_id, "confirmed_not_started", observer=" ", note=" ")

    report = InterruptedTaskReconciler().reconcile(snapshot, [invalid])

    assessment = report.assessments[0]
    assert report.has_blocking_findings
    assert assessment.recommendation == "keep_recovery_required"
    assert "observation_invalid" in assessment.finding_codes
    assert snapshot.tasks[0].state == "recovery_required"


def test_non_recovery_task_cannot_be_reconciled_as_interrupted():
    snapshot, task_id = _snapshot(state="pending")
    snapshot = replace(snapshot, pending_count=1, recovery_required_count=0)

    report = InterruptedTaskReconciler().reconcile(
        snapshot, [_observation(task_id, "confirmed_not_started")]
    )

    assert report.has_blocking_findings
    assert any(item.code == "task_not_recovery_required" for item in report.findings)
    assert snapshot.tasks[0].state == "pending"
