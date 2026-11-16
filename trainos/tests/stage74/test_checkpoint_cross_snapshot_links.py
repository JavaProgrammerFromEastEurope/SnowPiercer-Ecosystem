from dataclasses import replace

import pytest

from kernel.command.events.diagnostic_investigation_checkpoint import (
    DiagnosticInvestigationCheckpointService,
)
from kernel.command.events.diagnostic_investigation_store import (
    DiagnosticInvestigationStore,
    InvestigationStoreIntegrityError,
)
from tests.stage63.test_diagnostic_investigation_checkpoint import snapshots


def test_checkpoint_rejects_task_id_that_disagrees_with_hypothesis_and_definition(tmp_path):
    hypotheses, tasks = snapshots()
    corrupted_task = replace(tasks.tasks[0], task_id="h1::different_task")
    transitions = tuple(replace(t, task_id=corrupted_task.task_id) for t in tasks.transitions)
    corrupted_tasks = replace(tasks, tasks=(corrupted_task,), transitions=transitions)
    with DiagnosticInvestigationStore(tmp_path / "cross-links.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        with pytest.raises(InvestigationStoreIntegrityError, match="identity disagrees"):
            service.save_checkpoint("case-1", hypotheses, corrupted_tasks)
        assert service.load_checkpoint("case-1") is None


def test_checkpoint_rejects_duplicate_task_evidence_references(tmp_path):
    hypotheses, tasks = snapshots()
    corrupted_task = replace(tasks.tasks[0], evidence_event_ids=("event-1", "event-1"))
    corrupted_tasks = replace(tasks, tasks=(corrupted_task,))
    with DiagnosticInvestigationStore(tmp_path / "evidence-links.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        with pytest.raises(InvestigationStoreIntegrityError, match="invalid evidence event references"):
            service.save_checkpoint("case-1", hypotheses, corrupted_tasks)
        assert service.load_checkpoint("case-1") is None


def test_checkpoint_accepts_valid_cross_snapshot_identity(tmp_path):
    hypotheses, tasks = snapshots()
    with DiagnosticInvestigationStore(tmp_path / "valid-links.db") as store:
        service = DiagnosticInvestigationCheckpointService(store)
        saved = service.save_checkpoint("case-1", hypotheses, tasks)
        restored = service.restore_checkpoint_with_assessment("case-1")
        assert saved.revision == 1
        assert restored.is_successful
