from dataclasses import replace

import pytest

from kernel.command.events import (
    DiagnosticEvidenceRecoveryIntegrityVerifier,
    DiagnosticEvidenceTaskTracker,
)
from tests.domains.recovery.test_interrupted_task_recovery import tracker_with_interrupted_task


def _recovered_tracker():
    tracker, task_id = tracker_with_interrupted_task()
    tracker.mark_interrupted_tasks_for_recovery(actor="restart-manager")
    return tracker, task_id


def test_valid_recovery_history_is_consistent():
    tracker, _ = _recovered_tracker()
    report = DiagnosticEvidenceRecoveryIntegrityVerifier().verify(tracker.snapshot())
    assert report.is_consistent
    assert report.recovery_required_count == 1
    assert not report.findings


def test_explicit_recovery_resolution_is_recorded_and_consistent():
    tracker, task_id = _recovered_tracker()
    tracker.resolve_recovery_required(task_id, decision="block", actor="operator", note="external state reviewed")
    report = DiagnosticEvidenceRecoveryIntegrityVerifier().verify(tracker.snapshot())
    assert report.is_consistent


def test_missing_recovery_entry_is_reported():
    tracker, _ = _recovered_tracker()
    snapshot = tracker.snapshot()
    bad = replace(snapshot, transitions=snapshot.transitions[:-1], total_transitions=snapshot.total_transitions - 1)
    report = DiagnosticEvidenceRecoveryIntegrityVerifier().verify(bad)
    codes = {item.code for item in report.findings}
    assert "current_state_history_mismatch" in codes
    assert "recovery_entry_missing" in codes


def test_recovery_exit_without_decision_note_is_reported():
    tracker, task_id = _recovered_tracker()
    tracker.resolve_recovery_required(task_id, decision="block", actor="operator", note="external state reviewed")
    snapshot = tracker.snapshot()
    last = replace(snapshot.transitions[-1], note="blocked by operator")
    snapshot = replace(snapshot, transitions=snapshot.transitions[:-1] + (last,))
    report = DiagnosticEvidenceRecoveryIntegrityVerifier().verify(snapshot)
    assert "recovery_decision_record_invalid" in {item.code for item in report.findings}
    assert not report.is_consistent


def test_transition_timestamp_requires_timezone():
    tracker, _ = _recovered_tracker()
    snapshot = tracker.snapshot()
    first = replace(snapshot.transitions[0], timestamp_iso="2026-10-20T12:00:00")
    snapshot = replace(snapshot, transitions=(first,) + snapshot.transitions[1:])
    report = DiagnosticEvidenceRecoveryIntegrityVerifier().verify(snapshot)
    assert "transition_timestamp_invalid" in {item.code for item in report.findings}


def test_state_counts_and_transition_sequence_are_checked():
    tracker, _ = _recovered_tracker()
    snapshot = tracker.snapshot()
    transitions = (replace(snapshot.transitions[0], sequence=9),) + snapshot.transitions[1:]
    snapshot = replace(snapshot, transitions=transitions, pending_count=99)
    report = DiagnosticEvidenceRecoveryIntegrityVerifier().verify(snapshot)
    codes = {item.code for item in report.findings}
    assert {"transition_sequence_invalid", "state_count_mismatch"} <= codes


def test_rejects_wrong_snapshot_type():
    with pytest.raises(TypeError):
        DiagnosticEvidenceRecoveryIntegrityVerifier().verify(object())
