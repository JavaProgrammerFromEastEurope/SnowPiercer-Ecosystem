from dataclasses import replace

import pytest

from kernel.command.events import (
    EvidenceCollectionTask,
    EvidenceTaskTrackerSnapshot,
    TrackedEvidenceTask,
    InterruptedTaskObservation,
    InterruptedTaskReconciler,
)


def recovered_snapshot(attempts=1, max_attempts=3, state="recovery_required"):
    task_id = "hypothesis-1::recover_event"
    task = TrackedEvidenceTask(
        task_id=task_id, hypothesis_id="hypothesis-1",
        task=EvidenceCollectionTask("recover_event", "normal", "Recover missing event", True),
        state=state, attempts=attempts, max_attempts=max_attempts,
        result_note="interrupted", updated_at_iso="2026-10-20T12:00:00+00:00",
    )
    snapshot = EvidenceTaskTrackerSnapshot(
        tasks=(task,), transitions=(), total_registered=1, total_transitions=2,
        pending_count=int(state == "pending"), in_progress_count=int(state == "in_progress"),
        completed_count=int(state == "completed"), blocked_count=int(state == "blocked"),
        recovery_required_count=int(state == "recovery_required"),
    )
    return snapshot, task_id


def observation(task_id, status="confirmed_not_started", **kwargs):
    defaults = dict(
        task_id=task_id, observation_status=status,
        observed_at_iso="2026-10-20T12:00:00+00:00", observer="operator-1",
        note="Checked authoritative execution records", evidence_ids=("audit-record-1",),
    )
    defaults.update(kwargs)
    return InterruptedTaskObservation(**defaults)


def test_confirmed_not_started_recommends_reviewed_retry_without_mutation():
    snapshot, task_id = recovered_snapshot()
    before = snapshot
    report = InterruptedTaskReconciler().reconcile(before, [observation(task_id)])
    assert report.assessments[0].recommendation == "safe_to_retry_after_authorized_review"
    assert snapshot == before


def test_attempt_limit_exhaustion_prevents_retry_recommendation():
    snapshot, task_id = recovered_snapshot(attempts=3, max_attempts=3)
    report = InterruptedTaskReconciler().reconcile(snapshot, [observation(task_id)])
    assert report.assessments[0].recommendation == "require_block_or_manual_review"
    assert "retry_limit_exhausted" in report.assessments[0].finding_codes


@pytest.mark.parametrize(("status", "recommendation"), [
    ("partial_or_unknown", "keep_recovery_required"),
    ("external_effect_detected", "keep_recovery_required_and_reconcile_external_effects"),
    ("confirmed_completed", "completed_outcome_requires_independent_verification"),
])
def test_ambiguous_or_completed_external_outcomes_are_never_applied_automatically(status, recommendation):
    snapshot, task_id = recovered_snapshot()
    report = InterruptedTaskReconciler().reconcile(snapshot, [observation(task_id, status)])
    assert report.assessments[0].recommendation == recommendation
    assert snapshot.tasks[0].state == "recovery_required"


def test_missing_observation_keeps_task_in_recovery_required():
    snapshot, task_id = recovered_snapshot()
    report = InterruptedTaskReconciler().reconcile(snapshot, [])
    assert report.assessments[0].recommendation == "keep_recovery_required"
    assert "observation_missing" in report.assessments[0].finding_codes


def test_duplicate_unknown_and_non_recovery_observations_are_reported():
    snapshot, task_id = recovered_snapshot()
    item = observation(task_id)
    unknown = observation("not-a-task")
    report = InterruptedTaskReconciler().reconcile(snapshot, [item, item, unknown])
    codes = {finding.code for finding in report.findings}
    assert {"duplicate_observations", "unknown_task"} <= codes
    other = replace(snapshot, tasks=tuple(replace(t, state="pending") for t in snapshot.tasks), recovery_required_count=0, pending_count=1)
    report2 = InterruptedTaskReconciler().reconcile(other, [item])
    assert "task_not_recovery_required" in {finding.code for finding in report2.findings}


def test_invalid_observation_fields_are_blocking_and_never_recommend_retry():
    snapshot, task_id = recovered_snapshot()
    bad = observation(task_id, observation_status=[], observed_at_iso="yesterday", observer=" ", note=" ", evidence_ids=("x", "x"))
    report = InterruptedTaskReconciler().reconcile(snapshot, [bad])
    assert report.has_blocking_findings
    assert report.assessments[0].recommendation == "keep_recovery_required"


def test_rejects_invalid_input_types():
    with pytest.raises(TypeError):
        InterruptedTaskReconciler().reconcile(object(), [])
    snapshot, _ = recovered_snapshot()
    with pytest.raises(TypeError):
        InterruptedTaskReconciler().reconcile(snapshot, [object()])
