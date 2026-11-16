from dataclasses import replace
import sqlite3

from kernel.command.events import (
    DiagnosticInvestigationCheckpointService,
    DiagnosticInvestigationStore,
)
from tests.stage63.test_diagnostic_investigation_checkpoint import snapshots


def test_restart_restore_assessment_returns_fresh_instances(tmp_path):
    hypotheses, tasks = snapshots()
    path = tmp_path / "restart.db"
    with DiagnosticInvestigationStore(path) as store:
        DiagnosticInvestigationCheckpointService(store).save_checkpoint("case", hypotheses, tasks)

    with DiagnosticInvestigationStore(path) as reopened:
        result = DiagnosticInvestigationCheckpointService(reopened).restore_checkpoint_with_assessment("case")

    assert result.is_successful
    assert result.restored is not None
    assert result.restored.checkpoint.hypotheses == hypotheses
    assert result.restored.checkpoint.tasks == tasks
    # A successful restore returns newly reconstructed domain instances, not a cached object.
    assert result.restored.task_tracker is not None


def test_bad_transition_timestamp_rejects_restore_without_partial_objects(tmp_path):
    hypotheses, tasks = snapshots()
    invalid_transition = replace(tasks.transitions[0], timestamp_iso="2026-10-20T10:00:00")
    invalid_tasks = replace(tasks, transitions=(invalid_transition,))
    with DiagnosticInvestigationStore(tmp_path / "invalid-history.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case", hypotheses, invalid_tasks)
        result = service.restore_checkpoint_with_assessment("case")

    assert not result.is_successful
    assert result.restored is None
    assert result.error_code == "task_recovery_history_inconsistent"
    assert result.integrity_report is not None
    assert "transition_timestamp_invalid" in {f.code for f in result.integrity_report.findings}


def test_database_payload_tampering_is_detected_after_reopen(tmp_path):
    hypotheses, tasks = snapshots()
    path = tmp_path / "tampered.db"
    with DiagnosticInvestigationStore(path) as store:
        DiagnosticInvestigationCheckpointService(store).save_checkpoint("case", hypotheses, tasks)

    # Simulate an out-of-band edit that does not update the checksum chain.
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE investigation_record_versions SET payload_json=? WHERE record_type=? AND record_id=? AND revision=1",
            ('{"schema_version":999}', "diagnostic_investigation_checkpoint", "case"),
        )
        connection.commit()
    finally:
        connection.close()

    with DiagnosticInvestigationStore(path) as reopened:
        result = DiagnosticInvestigationCheckpointService(reopened).restore_checkpoint_with_assessment("case")
        issues = reopened.verify_integrity()

    assert not result.is_successful
    assert result.restored is None
    assert result.error_code == "checkpoint_integrity_rejected"
    assert any(issue.code == "checksum_mismatch" for issue in issues)


def test_restore_capacity_failure_does_not_return_partial_state(tmp_path):
    hypotheses, tasks = snapshots()
    with DiagnosticInvestigationStore(tmp_path / "capacity.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case", hypotheses, tasks)
        result = service.restore_checkpoint_with_assessment("case", max_tasks=0)

    assert not result.is_successful
    assert result.restored is None
    assert result.error_code == "checkpoint_payload_invalid"
