import pytest

from kernel.command.events import (
    CheckpointRestoreAssessment,
    DiagnosticInvestigationCheckpointService,
    DiagnosticInvestigationStore,
    InvestigationStoreIntegrityError,
)
from tests.stage63.test_diagnostic_investigation_checkpoint import snapshots


def test_assessed_restore_returns_integrity_report_for_valid_checkpoint(tmp_path):
    hypotheses, tasks = snapshots()
    with DiagnosticInvestigationStore(tmp_path / "case.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case-69", hypotheses, tasks)
        result = service.restore_checkpoint_with_assessment("case-69")

    assert isinstance(result, CheckpointRestoreAssessment)
    assert result.is_successful
    assert result.restored is not None
    assert result.integrity_report is not None
    assert result.integrity_report.is_consistent
    assert result.integrity_report.task_count == 1


def test_assessed_restore_reports_missing_checkpoint_without_throwing(tmp_path):
    with DiagnosticInvestigationStore(tmp_path / "case.db") as store:
        result = DiagnosticInvestigationCheckpointService(store).restore_checkpoint_with_assessment("missing")

    assert not result.is_successful
    assert result.restored is None
    assert result.error_code == "checkpoint_not_found"


def test_assessed_restore_rejects_corrupt_checkpoint_with_structured_code(tmp_path):
    hypotheses, tasks = snapshots()
    with DiagnosticInvestigationStore(tmp_path / "case.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        service.save_checkpoint("case-69", hypotheses, tasks)
        # The persisted chain is immutable through the public API. Simulate a
        # checkpoint whose payload is structurally invalid at the domain boundary.
        record = store.load(service.RECORD_TYPE, "case-69")
        assert record is not None
        bad_payload = dict(record.payload)
        bad_payload["schema_version"] = 999
        # A new record with the bad schema remains checksum-valid, so the checkpoint
        # decoder—not the store's checksum checker—must reject it.
        store.save(service.RECORD_TYPE, "bad-schema", bad_payload)
        result = service.restore_checkpoint_with_assessment("bad-schema")

    assert not result.is_successful
    assert result.restored is None
    assert result.error_code == "checkpoint_integrity_rejected"
    assert "schema version" in result.error_message


def test_assessed_restore_rejects_blank_id_as_programmer_error(tmp_path):
    with DiagnosticInvestigationStore(tmp_path / "case.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        with pytest.raises(ValueError):
            service.restore_checkpoint_with_assessment(" ")
